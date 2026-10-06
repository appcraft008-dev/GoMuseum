"""识别编排:校验/哈希 → 缓存 → vision(引擎位,P2 换 CLIP) → 目录匹配 → 三档分流。
R1 接地:响应里的身份只可能来自目录命中;不中诚实 unrecognized + 记需求(R5)。
spec docs/superpowers/specs/2026-07-03-recognition-design.md。"""

from __future__ import annotations

import hashlib
import io
import json
import logging
import time

import redis as redis_lib

from app.core.config import settings
from app.models.artist import Artist
from app.models.museum import Museum
from app.models.museum_object import MuseumObject, ObjectImage
from app.services.museum_repo import _photo_credit, _resolve_name, _sized
from app.services.recognition.demands import record_demand
from app.services.recognition.events import record_event
from app.services.recognition.matcher import LOW, build_index, inv_artist_hit, match
from app.services.recognition.vector_index import query_index
from app.services.recognition.vision import identify

logger = logging.getLogger(__name__)

_CACHE_TTL_MATCH = 30 * 86400  # 命中稳定:30天
_CACHE_TTL_MISS = 86400  # 未收录:目录会生长,只缓 1 天


def _cache_key(slug: str | None, sha: str, language: str, visible=None) -> str:
    # 可见馆集合进键:预览者的结果(可能含隐身馆藏品)不会被普通用户命中;
    # 放出新馆后集合变了,旧键自然作废,不需要清缓存。
    vtag = (
        "all"
        if visible is None
        else hashlib.md5(
            ",".join(sorted(str(v) for v in visible)).encode()
        ).hexdigest()[:8]
    )
    # 引擎进键:换模型(v2→v3 那种)后旧引擎的结果不能再被命中。
    return f"recog3:{slug or 'global'}:{settings.RECOG_MODEL}:{language}:{vtag}:{sha}"


def _drop_hidden(db, ranked: list, visible) -> list:
    """去掉隐身馆的藏品(可见性闸)。向量索引是进程内缓存、不带可见性,在这里按
    一份新鲜的可见集合过滤;隐身馆通常只有一家,查它的 qid 集合比回查全部命中便宜。"""
    if visible is None or not ranked:
        return ranked
    hidden = {
        r[0]
        for r in db.query(MuseumObject.qid).filter(
            MuseumObject.museum_id.notin_(visible)
        )
    }
    return [(q, s) for q, s in ranked if q not in hidden] if hidden else ranked


def _open_upright(image_bytes: bytes):
    """解码上传图并应用 EXIF 方向。手机竖拍 JPEG 像素横存+Orientation 标记,
    PIL 默认无视 → 嵌入'躺着'的画,相似度崩塌(实证:卧室 0.85→0.47,prod 三连miss)。"""
    from PIL import Image, ImageOps

    img = Image.open(io.BytesIO(image_bytes))
    return ImageOps.exif_transpose(img)


def _default_embed(image_bytes: bytes):
    """默认 embed_fn:包装 DINOv2 引擎。引擎不可用/解码或推理异常 → None(编排层走 GPT 兜底)。
    validate_image 的 PIL verify() 不解码像素——截断 JPEG 会过校验、在此处才爆,不许炸出去。"""
    from app.services.recognition.embedder import get_embedder

    engine = get_embedder()
    if engine is None:
        return None
    try:
        return engine.embed(_open_upright(image_bytes))
    except Exception:
        logger.exception("embed failed, falling back to GPT chain")
        return None


def _default_embed_crops(image_bytes: bytes):
    """默认 embed_crops_fn:裁剪金字塔批量 embedding。引擎不可用/异常 → None(编排层走 GPT 兜底)。"""
    from app.services.recognition.embedder import crop_pyramid, get_embedder

    engine = get_embedder()
    if engine is None:
        return None
    try:
        img = _open_upright(image_bytes)
        return engine.embed_batch(crop_pyramid(img))
    except Exception:
        logger.exception("embed_crops failed, falling back to GPT chain")
        return None


def _default_embed_canvas(image_bytes: bytes):
    """默认 embed_canvas_fn:找画布四边形→拉正→批量 embedding。无框/引擎不可用/异常 → None。
    先找框再取引擎:无框(纯色图、雕塑常见)时不碰引擎。"""
    from app.services.recognition.canvas import canvas_quads
    from app.services.recognition.embedder import get_embedder

    try:
        quads = canvas_quads(_open_upright(image_bytes))
        if not quads:
            return None
        engine = get_embedder()
        if engine is None:
            return None
        return engine.embed_batch(quads)
    except Exception:
        logger.exception("embed_canvas failed, continuing without canvas crops")
        return None


# 进程内单例 + 失败冷却。🔴 2026-10-05 前这里 import 一个不存在的
# `get_cache_service`,ImportError 被下面的 except 吞掉 → 恒 None → prod 识别缓存
# 从上线起一次都没命中过(0 条 engine=cache):同图重发=重算、匿名同图重拍=再扣次。
_redis_state: dict = {"client": None, "failed_at": None}
_REDIS_RETRY_S = 60


def _get_redis():
    st = _redis_state
    if st["client"] is not None:
        return st["client"]
    if (
        st["failed_at"] is not None
        and time.monotonic() - st["failed_at"] < _REDIS_RETRY_S
    ):
        return None  # 冷却期:Redis 挂了不让每次识别都等一次连接超时
    try:
        client = redis_lib.Redis(
            host=settings.REDIS_HOST,
            port=settings.REDIS_PORT,
            db=settings.REDIS_DB,
            password=settings.REDIS_PASSWORD,
            decode_responses=True,
            socket_connect_timeout=1,
            socket_timeout=1,  # 缓存是加速件,抖动时宁可算一遍也不卡 5 秒
        )
        client.ping()
    except Exception:
        logger.warning(
            "recognition cache: redis unavailable, retry in %ss", _REDIS_RETRY_S
        )
        st["failed_at"] = time.monotonic()
        return None
    st["client"], st["failed_at"] = client, None
    return client


# S2 同键在途合并:App 超时后用同一张照片重发时,首请求在服务端往往还在算
# (同步端点不随客户端断开而停)。第二个同键请求不重算,等首请求的结果。
_INFLIGHT_TTL_S = 150  # 锁自身过期:进程被杀也不留死锁;须长于最慢一次识别
_WAIT_CAP_S = 90  # 等待者上限:短于 nginx proxy_read_timeout 120s
_WAIT_POLL_S = 0.5


def _inflight_key(ckey: str) -> str:
    return ckey + ":inflight"


def _wait_inflight(redis, ckey: str) -> str | None:
    """轮询等首请求写缓存。锁消失(首请求已结束)仍无缓存、或到上限 → None,调用方自己算。
    不靠「缓存里出现值」判完成:写缓存失败被吞时首请求照常返回,缓存永远不会出现。
    ponytail: 等待占一个线程池线程(同步端点),最多 90s;并发重发多到占满线程池时改异步等待。
    """
    deadline = time.monotonic() + _WAIT_CAP_S
    while time.monotonic() < deadline:
        time.sleep(_WAIT_POLL_S)
        hit = redis.get(ckey)
        if hit:
            return hit
        if not redis.exists(_inflight_key(ckey)):
            return redis.get(ckey)  # 两次读之间首请求恰好写完缓存并释放锁
    return None


def _summary(db, storage, o: MuseumObject, language: str) -> dict:
    attrs = o.attributes or {}
    art = None
    if attrs.get("artist_qid"):
        art = db.query(Artist).filter_by(qid=attrs["artist_qid"]).first()
    img = (
        db.query(ObjectImage)
        .filter_by(object_id=o.id, role="primary")
        .order_by(ObjectImage.sort)
        .first()
    )
    mus = db.query(Museum).filter_by(id=o.museum_id).first()
    return _summary_of(storage, o, art, img, mus, language)


def _summaries(db, storage, objs: list, language: str) -> dict:
    """批量版 [_summary]:{qid: summary}。作者/主图/馆各一次查询,不随件数增长
    (足迹逐件调 _summary 时 191 件 = 567 条 SQL,prod 实测约 1 秒)。
    字段拼法只在 [_summary_of] 一处,两条路径不会漂开。"""
    if not objs:
        return {}
    aqids = {(o.attributes or {}).get("artist_qid") for o in objs} - {None}
    arts = (
        {a.qid: a for a in db.query(Artist).filter(Artist.qid.in_(aqids))}
        if aqids
        else {}
    )
    imgs: dict = {}
    for im in (
        db.query(ObjectImage)
        .filter(
            ObjectImage.object_id.in_([o.id for o in objs]),
            ObjectImage.role == "primary",
        )
        .order_by(ObjectImage.object_id, ObjectImage.sort)
    ):
        imgs.setdefault(im.object_id, im)  # 每件 sort 最小那张,同 _summary
    muss = {
        m.id: m
        for m in db.query(Museum).filter(Museum.id.in_({o.museum_id for o in objs}))
    }
    return {
        o.qid: _summary_of(
            storage,
            o,
            arts.get((o.attributes or {}).get("artist_qid")),
            imgs.get(o.id),
            muss.get(o.museum_id),
            language,
        )
        for o in objs
    }


def _summary_of(storage, o: MuseumObject, art, img, mus, language: str) -> dict:
    attrs = o.attributes or {}
    thumbnail = image = credit = None
    if img and img.image_key:
        thumbnail = _sized(storage, img.image_key, "thumb")
        image = _sized(storage, img.image_key, "large")
    elif img:
        thumbnail = image = img.source_url
    if img:
        # 同详情页图集:CC 署名要留,作者本人不算署名(见 _photo_credit)
        credit = _photo_credit(
            img.credit,
            {
                *((art.name_i18n or {}).values() if art else ()),
                *((art.name_zh, art.name_en) if art else ()),
                o.artist_zh,
                o.artist_en,
            },
        )
    return {
        "qid": o.qid,
        "museum": mus.slug if mus else None,
        "title": _resolve_name(
            attrs.get("title_i18n"),
            language,
            {"zh": o.title_zh, "en": o.title_en},
            o.title_en or o.title_zh or o.qid,
        ),
        "artist": _resolve_name(
            art.name_i18n if art else None,
            language,
            {"zh": o.artist_zh, "en": o.artist_en},
            o.artist_en or o.artist_zh,
        ),
        "thumbnail": thumbnail,
        # S3 加法字段:候选全屏比对用大图 + 署名(老 App 不读)
        "image": image,
        "credit": credit,
    }


def _vector_out(db, storage, ranked: list, language: str) -> dict | None:
    """向量检索 [(qid,score)] → 输出 dict(match/candidates);top<LOW 或空 → None(触发下一档)。
    纯向量命中:未调 GPT,label_text/reason 恒 None。"""
    if not ranked:
        return None
    top_score = ranked[0][1]
    # 第二名紧咬(姊妹作、同图挂两个条目)→ 不直判,落到下面的候选档让用户挑
    close = len(ranked) > 1 and top_score - ranked[1][1] < settings.RECOG_MARGIN
    if top_score >= settings.RECOG_HIGH and not close:
        o = db.query(MuseumObject).filter_by(qid=ranked[0][0]).one()
        return {
            "outcome": "match",
            "match": {
                **_summary(db, storage, o, language),
                "confidence": round(top_score, 3),
            },
            "candidates": [],
            "label_text": None,
            "reason": None,
        }
    if top_score >= settings.RECOG_LOW:
        cands = []
        for qid, score in ranked[:3]:
            if score < settings.RECOG_LOW:
                break
            o = db.query(MuseumObject).filter_by(qid=qid).one()
            cands.append(
                {**_summary(db, storage, o, language), "score": round(score, 3)}
            )
        return {
            "outcome": "candidates",
            "match": None,
            "candidates": cands,
            "label_text": None,
            "reason": None,
        }
    return None


class _StageClock:
    """识别分步计时(S1)。mark(name) 记「上一个打点到现在」的毫秒数。
    ponytail: 只记跑了的阶段,同名重复 mark 会覆盖——recognize() 里每个阶段只 mark 一次。"""

    def __init__(self):
        self._t0 = self._last = time.perf_counter()
        self.stages: dict[str, int] = {}

    def mark(self, name: str) -> None:
        now = time.perf_counter()
        self.stages[name] = round((now - self._last) * 1000)
        self._last = now

    def total_ms(self) -> int:
        return round((time.perf_counter() - self._t0) * 1000)


def _top_of(out: dict) -> tuple:
    """从响应 dict 取 (top_qid, top_score) 供埋点;三档统一。"""
    m = out.get("match")
    if m:
        return m.get("qid"), m.get("confidence")
    cands = out.get("candidates") or []
    if cands:
        return cands[0].get("qid"), cands[0].get("score")
    return None, None


def _compute(
    db,
    slug,
    museum,
    image_bytes: bytes,
    *,
    phash,
    language,
    mode,
    identify_fn,
    embed_fn,
    vector_query_fn,
    embed_crops_fn,
    embed_canvas_fn,
    user_id,
    visible,
    redis,
    ckey,
    clock,
) -> dict:
    """缓存未命中后的真识别:向量三档 → GPT+文字兜底 → 记事件 → 写缓存。"""
    from app.services.image_service import ImageService
    from app.services.storage import get_object_storage

    storage = get_object_storage()
    museum_id = museum.id if museum else None

    out = None
    vis = None
    engine = "none"  # 埋点:决出结果的档位
    # --- 向量前置(仅 artwork;label 纯转写直走 GPT 链) ---
    if mode == "artwork":
        vec = (embed_fn or _default_embed)(image_bytes)
        clock.mark("embed")
        if vec is not None:
            vquery = vector_query_fn or query_index
            ranked = vquery(db, vec, museum_id)
            clock.mark("vq")

            def _merge(ranked, vecs):  # 跨全帧+补查按 qid 取 MAX,重定档
                agg = dict(ranked)
                for cv in vecs:
                    for qid, s in vquery(db, cv, museum_id):
                        if s > agg.get(qid, -2.0):
                            agg[qid] = s
                return sorted(agg.items(), key=lambda kv: -kv[1])

            canvas_used = crops_used = False
            # 画框+墙挤占画面的对症药(蒙娜丽莎正面照 第46名→第1名);斜拍梯形顺带拉正。
            # 全帧未到 HIGH 就跑:候选档(0.72-0.85)的照片也能升到直判。
            if not ranked or ranked[0][1] < settings.RECOG_HIGH:
                canvas = (embed_canvas_fn or _default_embed_canvas)(image_bytes)
                if canvas is not None:
                    canvas_used = True
                    ranked = _merge(ranked, canvas)
                clock.mark("canvas")
            # 全景式拍法(画占画面小)的对症药——实测 0.509→0.847;怼拍照片不受影响(快路径)。
            # 已 ≥ LOW → 不跑金字塔。
            if not ranked or ranked[0][1] < settings.RECOG_LOW:
                crops = (embed_crops_fn or _default_embed_crops)(image_bytes)
                if crops is not None:
                    crops_used = True
                    ranked = _merge(ranked, crops)
                clock.mark("crops")
            ranked = _drop_hidden(db, ranked, visible)
            out = _vector_out(db, storage, ranked, language)
            clock.mark("vector_out")
            if out is not None:
                engine = (
                    "vector_crops"
                    if crops_used
                    else "vector_canvas" if canvas_used else "vector"
                )
            # 馆域调用不回退全局:老端点已部署 App 不读 museum 字段,跨馆命中会拿他馆
            # qid 撞 /{slug}/objects/{qid}/content 404 死胡同(前向兼容硬约束)。
            # 将来带馆提示的新调用方要全局回退时,加显式参数再开;slug=None 首查即全局。

    text_trace = None  # 文字链复盘用:AI 读出了什么、匹配给了什么(向量路径为 None)
    if out is None:  # --- GPT + OCR 兜底链(原样) ---
        engine = "text"
        from app.services.recognition.vision import _shrink

        identify_fn = identify_fn or identify
        vis = identify_fn(ImageService.to_base64(_shrink(image_bytes)), mode=mode)
        text_trace = {"vision": vis, "matched": []}
        clock.mark("gpt")
        queries = [c["title"] for c in vis["candidates"] if c.get("title")]
        # 作者名只作加分线索,绝不当标题探针(肖像画劫持教训,见 matcher.match)
        artist_hints = [c["artist"] for c in vis["candidates"] if c.get("artist")]
        label_lines = (vis.get("label_text") or "").splitlines()
        label_lines = [ln.strip() for ln in label_lines if ln.strip()]

        out = {
            "outcome": "unrecognized",
            "match": None,
            "candidates": [],
            "label_text": vis.get("label_text"),
            "reason": None,
        }
        if not queries and not label_lines:
            out["reason"] = "no_candidates"
        else:
            index = build_index(db, museum_id)
            if visible is not None:
                index = [e for e in index if e["museum_id"] in visible]
            # 馆藏号 + 作者双重吻合 → 直判,模糊匹配不用跑(编号是墙签上最准的线索)
            inv_hit = inv_artist_hit(index, queries + label_lines, artist_hints)
            text_trace["inv_hit"] = inv_hit
            # 墙签模式:AI 已摘出印着的标题 → 只拿它匹配;整段墙签行只用来抽馆藏号
            results = (
                [(inv_hit, 1.0)]
                if inv_hit
                else match(
                    index,
                    queries,
                    label_lines,
                    artist_hints,
                    label_lines_inv_only=mode == "label" and bool(queries),
                )
            )
            text_trace["matched"] = [[q, round(sc, 3)] for q, sc in results[:5]]
            top = results[0] if results else None
            # 文字链证据=名字对上≠就是这件(同名撞车 E2E 实证:自画像/The Bathers);
            # 直判只属于向量像素证据,唯一例外是馆藏号+作者双重吻合(inv_hit)。
            if inv_hit:
                o = db.query(MuseumObject).filter_by(qid=inv_hit).one()
                out["outcome"] = "match"
                out["match"] = {**_summary(db, storage, o, language), "confidence": 1.0}
            elif top and top[1] >= LOW:
                out["outcome"] = "candidates"
                for qid, score in results[:3]:
                    if score < LOW:
                        break
                    o = db.query(MuseumObject).filter_by(qid=qid).one()
                    out["candidates"].append(
                        {**_summary(db, storage, o, language), "score": round(score, 3)}
                    )
            elif not results:
                out["reason"] = "not_in_catalog"
            else:
                out["reason"] = "low_confidence"
        clock.mark("match")

    if out["outcome"] == "unrecognized":  # 仅 GPT 链会到此,vis 必有值
        try:
            record_demand(
                db,
                slug,
                phash,
                label_text=vis.get("label_text"),
                candidates=vis["candidates"] or None,
                language=language,
            )
        except Exception:
            logger.exception("record_demand failed")
        clock.mark("demand")

    out["phash"] = phash  # 三档都带;缓存写入前放进 out,缓存命中的响应体也有
    tq, ts = _top_of(out)
    record_event(
        db,
        museum_slug=slug,
        phash=phash,
        outcome=out["outcome"],
        top_qid=tq,
        top_score=ts,
        language=language,
        engine=engine,
        user_id=user_id,
        duration_ms=clock.total_ms(),
        timings=clock.stages,
        text_trace=text_trace,
    )

    if redis is not None:
        try:
            ttl = _CACHE_TTL_MATCH if out["outcome"] == "match" else _CACHE_TTL_MISS
            redis.setex(ckey, ttl, json.dumps(out, ensure_ascii=False))
        except Exception:
            pass
    return out


def recognize(
    db,
    slug: str | None,
    image_bytes: bytes,
    *,
    language: str = "zh",
    mode: str = "artwork",
    identify_fn=None,
    redis=None,
    embed_fn=None,
    vector_query_fn=None,
    embed_crops_fn=None,
    embed_canvas_fn=None,
    user_id=None,
    visible=None,
) -> dict | None:
    """拍照识别:DINOv2 向量前置(三档)→ miss 则 GPT+OCR 兜底。
    slug=None → 全局(不查馆、不过滤);slug 给了但馆不存在 → None(老语义)。
    响应形状见 spec(outcome/reason 机器码)。"""
    clock = _StageClock()
    museum = None
    if slug is not None:
        museum = db.query(Museum).filter_by(slug=slug).one_or_none()
        if museum is None:
            return None
    from app.services.image_service import ImageService

    ImageService.validate_image(image_bytes)
    sha = ImageService.generate_hash(image_bytes)
    phash = ImageService.generate_perceptual_hash(image_bytes)
    clock.mark("prep")

    redis = redis if redis is not None else _get_redis()
    ckey = _cache_key(slug, sha, language, visible)
    owns_lock = False
    if redis is not None:
        try:
            hit = redis.get(ckey)
            clock.mark("cache_get")
            if not hit:
                owns_lock = bool(
                    redis.set(_inflight_key(ckey), "1", nx=True, ex=_INFLIGHT_TTL_S)
                )
                if not owns_lock:
                    try:
                        hit = _wait_inflight(redis, ckey)
                    finally:  # 轮询中途 Redis 掉线,等待耗时也记在这里
                        clock.mark("inflight_wait")
            if hit:
                cached_out = json.loads(hit)
                # 缓存命中:计费层据此不扣次。等来的是在途首请求的结果 → "inflight",
                # 计费层对它一律不扣(首请求自己会扣/解锁,见 recognize_billed)
                cached_out["_billed"] = (
                    "inflight" if "inflight_wait" in clock.stages else True
                )
                cached_out["phash"] = phash  # 升级前旧缓存条目无 phash,命中时补齐
                tq, ts = _top_of(cached_out)
                record_event(
                    db,
                    museum_slug=slug,
                    phash=phash,
                    outcome=cached_out.get("outcome"),
                    top_qid=tq,
                    top_score=ts,
                    language=language,
                    engine="cache",
                    user_id=user_id,
                    duration_ms=clock.total_ms(),
                    timings=clock.stages,
                )
                return cached_out
        except Exception:
            # 缓存不可用不阻断识别;超时那段也记在 cache_get,别算到下一阶段头上。
            # 已记过(get 成功、之后加锁/等待才出错)就别覆盖:同名 mark 是覆盖语义
            if "cache_get" not in clock.stages:
                clock.mark("cache_get")

    try:
        return _compute(
            db,
            slug,
            museum,
            image_bytes,
            phash=phash,
            language=language,
            mode=mode,
            identify_fn=identify_fn,
            embed_fn=embed_fn,
            vector_query_fn=vector_query_fn,
            embed_crops_fn=embed_crops_fn,
            embed_canvas_fn=embed_canvas_fn,
            user_id=user_id,
            visible=visible,
            redis=redis,
            ckey=ckey,
            clock=clock,
        )
    finally:
        # 独立 finally:首请求成功、异常、写缓存失败,锁都必须放掉(等待者靠它判结束)
        if owns_lock:
            try:
                redis.delete(_inflight_key(ckey))
            except Exception:
                logger.warning("recognition inflight lock release failed: %s", ckey)


class QuotaExceededError(Exception):
    """识别配额用尽(端点映射 402;缓存命中也拦——付费墙语义)。
    [museum] = 撞墙的那家馆(已知时),402 据此下发**该馆**该买的票。"""

    def __init__(self, museum=None):
        super().__init__()
        self.museum = museum


def _pass_active(db, user_id, museum=None) -> bool:
    """通票是否生效。权益真相源只有 entitlements 一处(见 entitlement_service)。
    [museum] 给了 = 只认覆盖这家馆的票(D7);不给 = 任意一张。
    无 user_id(游客/令牌失效)一律 False —— 票挂账号,设备身份上不可能有票。
    不吞异常:resolve_state 炸了该报 500,悄悄回退成"无票"会把付费用户打回 402。"""
    if not user_id:
        return False
    from app.services import entitlement_service as es

    return es.resolve_state(db, str(user_id), museum)[0] == es.ACTIVE


def _unlock_audio(db, user_id, out: dict) -> None:
    """识别成功 → 这件作品的主讲解段以后可免费听(2026-09-19 规则)。

    在**扣费的同一处**解锁:免费识别次数是唯一的那个数字,语音跟着它走,
    不再有第二个额度要对齐(旧规则「免费试听一件」与「免费识别 5 次」互不对齐,
    用户识别第二件点播放被弹墙,观感是那 5 次识别是假的)。

    只解 match:候选态这里既不扣费也不解锁,两件事一起挪到了用户点选某个候选
    之后(`/recognize/confirm`)—— 理由见 [recognize_billed]。

    匿名请求(只有 device_id)跳过:音频端点一律要令牌,解锁给谁都无处可用。
    解锁失败绝不能影响识别结果 —— 识别已经扣过费了。
    """
    if not user_id:
        return
    qids = []
    match = out.get("match") or {}
    if match.get("qid"):
        qids.append(match["qid"])
    if not qids:
        return
    try:
        from app.services.entitlement_service import unlock_free_audio

        unlock_free_audio(db, str(user_id), qids)
    except Exception:
        logger.exception("unlock_free_audio failed")


def recognize_billed(
    db,
    slug: str | None,
    image_bytes: bytes,
    *,
    user_id,
    device_id,
    language: str = "zh",
    mode: str = "artwork",
    identify_fn=None,
    redis=None,
    embed_fn=None,
    vector_query_fn=None,
    visible=None,
) -> dict | None:
    """带配额的识别(计费规则,用户 2026-07-04 批准 / 2026-09-20 修订):
    match 扣 1;unrecognized 不扣(不为失败付费);这件已解锁未过期时重拍不扣;
    配额用尽 → QuotaExceededError(先于 GPT 调用,不烧钱)。

    ⚠️ **票只在它覆盖的馆里不限次**(D7,spec 2026-09-28 §3.4,用户 2026-09-29 纠正):
    命中别处的馆 = 免费用户同价;额度也空了 → 402 并下发**那家馆**的票。

    ⚠️ **candidates 在这里不扣** —— 扣费点挪到用户点选某个候选之后
    (`POST /recognize/confirm`,幂等靠 `confirmed_qid`)。原先返回候选的当场就扣,
    而候选正是"识别器没把握"的那一档:用户点「都不是」时已经为一个错答案付过钱了,
    与本函数自己写的"不为失败付费"相矛盾(用户 2026-09-20 提出)。
    取舍:从不确认的候选请求不计费,因此存在"反复拍到候选就能不限次识别"的窗口
    —— 与删号刷额度同源(设备身份可刷,见 auth_service.delete_user_account),
    根治同样要靠 Play Integrity,MVP 接受。

    ⚠️ **通票生效期内不受免费额度限制** —— 不限次识别是卖给用户的权益。
    此前这道闸只问 BenefitsService(免费层额度),从不问 entitlements,于是
    付费用户免费额度一归零就被永久 402;而 entitlement_service.summary 的
    `can.recognize = active or left > 0` 按 active 放行 → 前端让按快门、
    后端拦下(prod 实证 2026-09-18:通票 active 的账号连撞 402)。
    权益真相源只有 entitlements 一处,这里跟它对齐。"""
    from app.services import entitlement_service as es
    from app.services.benefits_service import BenefitsService

    benefits = BenefitsService(db)
    # 前置闸(先于 GPT 调用,不烧钱):馆已知 → 只认覆盖它的票;全局识别还不知道是
    # 哪家馆 → 任意一张有效票先放行,范围在命中后判(D7)。
    scope_museum = None
    if slug is not None:
        scope_museum = db.query(Museum).filter_by(slug=slug).one_or_none()
    pass_ok = _pass_active(db, user_id, scope_museum)
    access = benefits.check_access(user_id, device_id)
    if not pass_ok and not access.get("has_access"):
        raise QuotaExceededError(scope_museum)
    out = recognize(
        db,
        slug,
        image_bytes,
        language=language,
        mode=mode,
        identify_fn=identify_fn,
        redis=redis,
        # 生产调用方不传(走默认 DINOv2);透传是为了让计费测试能造出真的 match ——
        # 不透传就只能 monkeypatch 掉 recognize 本身,那等于把被测的分流逻辑也蒙掉。
        embed_fn=embed_fn,
        vector_query_fn=vector_query_fn,
        user_id=user_id,  # 埋点顺带记足迹;device_id 不传(匿名就是匿名)
        visible=visible,
    )
    if out is None:
        return out
    cached = out.pop("_billed", None)  # 缓存命中标记(见 recognize)
    # S5 服务端开关(加法字段):App 只在它为 true 时才弹「发照片」确认框。
    # 隐私政策上线前 PHOTO_FEEDBACK_ENABLED=False → 恒 false,前端代码可以先发版。
    from app.services.storage import photo_feedback as pf

    out["photo_feedback"] = pf.photo_feedback_available()
    if out.get("outcome") != "match":
        return out
    if cached == "inflight":
        # S2:等来的是同一张照片在途首请求的结果,首请求自己会按规则扣次/解锁。
        # 这里再判就会撞上「首请求的解锁还没提交」→ 一张照片扣两次。
        # ponytail: 不区分首请求是不是同一个人(不同人同一时刻传同一份字节≈不存在);
        # 真要区分时把 user_id/device_id 写进锁值再比对。
        return out
    qid = (out.get("match") or {}).get("qid")
    museum = es.museum_of_qid(db, qid)
    # D7:**按命中的馆**判票。覆盖它 → 不限次,不扣额度,也不写免费解锁(D8:
    # 票本来就覆盖这件,过期自然锁)。不覆盖 → 与免费用户同价。
    # 否则买一张最便宜的票,到别的城市见一件拍一件就能白拿全部主讲解。
    if _pass_active(db, user_id, museum):
        return out
    if user_id and qid in es.free_audio_qids(
        benefits.get_or_create_benefits(user_id=user_id)
    ):
        return out  # 这件已解锁且未过期:重拍不再扣(替代原先按缓存命中免扣)
    if not user_id and cached:
        return out  # 匿名设备:同一张照片缓存命中不重复扣(老语义)
    try:
        charged = benefits.consume_recognition(user_id, device_id)
    except Exception:
        # 与改动前同语义:结果已算出,扣费故障不把用户打回 402
        logger.exception("consume_recognition failed")
        charged = True
    if not charged:
        # 持别处的票、免费额度又用完:不给结果,弹**这家馆**的票
        raise QuotaExceededError(museum)
    _unlock_audio(db, user_id, out)
    return out
