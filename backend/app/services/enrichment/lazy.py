"""懒生成(路线图3c):stub 首次访问触发后台生成一次。
锁=attributes.lazy_lock_at(TTL 自愈);并发上限=进程级信号量;完成/失败均清锁。
不对外暴露中间状态——stub 期间前端照旧"待完善",生成完刷新即 ready(契约形状零变化)。
plan 2026-07-03-lazy-generation。"""

from __future__ import annotations

import logging
import threading
import time
import uuid
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from datetime import datetime, timedelta, timezone

from app.core.config import settings
from app.models.museum_object import MuseumObject
from app.services import ops_alert

logger = logging.getLogger(__name__)

_LOCK_TTL = timedelta(minutes=10)  # 崩溃自愈:超时视为死锁可重拿
# 补语言阶段(spec 2026-10-17):懒生成完成后按语言并行补齐该馆其余语言。
# 标记 attributes.lazy_fanout = {"at": 心跳时刻, "pending": [还没补完的语言]}。
# 心跳 = 每补完一门刷新 at:慢任务不会过期;进程被部署杀掉后最多空等 5 分钟。
_FANOUT_TTL = timedelta(minutes=5)
# ponytail: 进程级同时最多 LAZY_FANOUT_CONCURRENCY 件补语言,满了跳过不排队(其余语言回到按请求懒翻译)
_FANOUT_SEM = threading.Semaphore(settings.LAZY_FANOUT_CONCURRENCY)
_FANOUT_WORKERS = 4  # 每件按语言并行;2 件 × 4 = 最多 8 路 mini 调用
# 补语言写的段打自己的来源,不挤占懒生成日上限(计入的话 1000 段只够约 31 件/天);
# 但要有自己的上限,不靠"只跟在生成后面"推理封顶:en 用户触发时每件要补的语言更多。
# 3000 段 ÷ 每门约 3 段 ≈ 1000 门次 × $0.0035 ≈ 最坏 $3.5/天(spec §4.4)。
FANOUT_SOURCE = "ai_lazy_fanout"
_FANOUT_DAILY_SECTION_CAP = 3000
# ponytail: 进程级并发上限见 LAZY_CONCURRENCY,保护 API 响应与 LLM 限速;多 worker/量大再上队列
_SEM = threading.Semaphore(settings.LAZY_CONCURRENCY)
# 全局日上限(2026-09-20 安全审计):当天已生成段数达此值就不再点火。
# 300 → 1000(10-10 用户定):10-07/10-08 只靠运营者逛馆就顶满(301/315),之后打开的新件全
# 显示假「重试」到 UTC 零点。1000 段 ≈ 120 件 ≈ 最坏 $4-10/天。
# ponytail: 一条 count 查询,不建表不加字段。见 daily_budget_exhausted。
_LAZY_DAILY_SECTION_CAP = 1000
# 懒生成/懒翻译写的段打这个来源,日上限只数它。原先不分来源:2026-09-28 我批量
# 补译小皇宫 440 段把当天额度吃光,用户点开第 61 件的 7 门语言全被「预算用尽」跳过,
# App 显示错误。批量是运营者主动花的钱,不该挤掉用户那份。
LAZY_SOURCE = "ai_lazy"
# 每账号 / 每 IP 日上限(2026-10-11 方案 A)。单位与全站上限相同 = 段,
# 点火时按估算段数扣:prod 10-01~10-10 实测懒生成 7.2-8.9 段/件、懒翻译 2.7-3.0 段/次。
# 按"次数"计会让单 IP 100 次新生成 ≈ 800 段吃掉全站 80%(spec 第二节)。
WEIGHT_GENERATION = 8
WEIGHT_TRANSLATION = 3
# 值见 settings(默认 160/300/600 段)
CAP_PER_USER = (
    settings.CAP_PER_USER
)  # ≈20 件新生成;挡单账号,也挡同一 WiFi 下一个人吃光整个 IP
# ≈37 件;单 IP 最多吃全站 30%(游客)。⚠️对 IPv6/代理轮换无效,分布式只靠全站上限
CAP_PER_IP = settings.CAP_PER_IP
# 正式账号的 IP 层另计一份(键 lazy:ipr:):团体共用 WiFi 时游客用满不拦正式账号,反之亦然
CAP_PER_IP_REGISTERED = settings.CAP_PER_IP_REGISTERED
_CAP_TTL_S = 2 * 86400


def lock_active(obj: MuseumObject) -> bool:
    """活锁 = 正在懒生成/懒翻译(端点 generating 字段的信号源;过期/坏时间戳=死锁不算)。"""
    at = (obj.attributes or {}).get("lazy_lock_at")
    if not at:
        return False
    try:
        return datetime.now(timezone.utc) - datetime.fromisoformat(at) < _LOCK_TTL
    except ValueError:
        return False  # 坏时间戳当过期


def fanout_pending(obj: MuseumObject) -> list[str]:
    """补语言进行中、还没补完的语言;无标记/心跳超时/坏值 → []。"""
    f = (obj.attributes or {}).get("lazy_fanout") or {}
    try:
        if datetime.now(timezone.utc) - datetime.fromisoformat(f["at"]) >= _FANOUT_TTL:
            return []
    except (KeyError, TypeError, ValueError):
        return []
    return list(f.get("pending") or [])


def fanout_stale(obj: MuseumObject) -> bool:
    """有补语言标记但心跳已超时 = 进程中途死了(部署重启等);正常结束会清标记。"""
    f = (obj.attributes or {}).get("lazy_fanout")
    if not f:
        return False
    try:
        return (
            datetime.now(timezone.utc) - datetime.fromisoformat(f["at"]) >= _FANOUT_TTL
        )
    except (KeyError, TypeError, ValueError):
        return True


def generating_for(obj: MuseumObject, language) -> bool:
    """端点 generating 字段:整件在懒生成/懒翻译,或这门语言还在补语言阶段的 pending 里。
    ⚠️ 必须是"这门语言整门翻完前一直 true":App 在 false 时 keepAlive 缓存结果
    (catalog_providers.dart),只有 guide 就报 false 会让深度段永远看不到。"""
    return lock_active(obj) or language in fanout_pending(obj)


# 补语言期间有人打开的语言(Redis 集合,跨 uvicorn worker 共享):下一个空出来的线程先补它。
# 放 Redis 不放 attributes:请求路径上写 attributes 会和补语言的心跳互相覆盖。
_WANT_TTL_S = 600


def _want_key(qid: str) -> str:
    return f"lazy:fanout_want:{qid}"


def record_fanout_want(qid: str, language: str, redis=None) -> None:
    """记一笔"有人在等这门语言";Redis 不可用就算了(只是少了插队,语言照样会补)。"""
    r = redis if redis is not None else _redis()
    if r is None:
        return
    try:
        r.pipeline().sadd(_want_key(qid), language).expire(
            _want_key(qid), _WANT_TTL_S
        ).execute()
    except Exception:
        logger.warning("lazy fanout: 记录优先语言失败 qid=%s", qid, exc_info=True)


def _fanout_wanted(qid: str, redis) -> set:
    if redis is None:
        return set()
    try:
        return set(redis.smembers(_want_key(qid)))
    except Exception:
        return set()


def _set_fanout(db, obj: MuseumObject, pending) -> None:
    # 写前重读:音频锁也在同一个 attributes JSON 里读改写(lazy_audio),压小覆盖窗口
    db.refresh(obj)
    obj.attributes = {
        **(obj.attributes or {}),
        "lazy_fanout": {
            "at": datetime.now(timezone.utc).isoformat(),
            "pending": list(pending),
        },
    }
    db.commit()


def _clear_fanout(db, obj: MuseumObject) -> None:
    db.refresh(obj)
    attrs = dict(obj.attributes or {})
    attrs.pop("lazy_fanout", None)
    obj.attributes = attrs
    db.commit()


def try_acquire_lock(db, obj: MuseumObject, require_status=("stub",)) -> bool:
    """状态匹配且无活锁 → 落锁返回 True。乐观读写:竞态窗口极小,撞了最多浪费一次生成费。
    stub=懒生成入口;ready=懒翻译入口(该语言缺)。"""
    if obj.content_status not in require_status:
        return False
    if lock_active(obj):
        return False
    obj.attributes = {
        **(obj.attributes or {}),
        "lazy_lock_at": datetime.now(timezone.utc).isoformat(),
    }
    db.commit()
    return True


def _clear_lock(db, obj: MuseumObject) -> None:
    attrs = dict(obj.attributes or {})
    attrs.pop("lazy_lock_at", None)
    obj.attributes = attrs
    db.commit()


def _generate(db, qid: str, language: str | None = None) -> dict:
    """真实生成:组件工厂装配 + generate_object(置 ready/empty)。测试 monkeypatch 此处。
    language=触发者的请求语言 → lang_priority(排队首,最快看到自己的语言)。"""
    from app.services.enrichment.factory import build_generation_components
    from app.services.enrichment.pipeline import generate_object

    o = db.query(MuseumObject).filter_by(qid=qid).one()
    from app.models.museum import Museum

    m = db.query(Museum).filter_by(id=o.museum_id).one()
    c = build_generation_components(m.slug)
    _req = [language] if language and language != "en" else []
    return generate_object(
        db,
        qid,
        enricher=c["enricher"],
        gate=c["gate"],
        translator=c["translator"],
        target_langs=["en"] + _req,  # 英语轴心 + 请求语言(仅);其余走懒翻译
        model="gpt-4o-mini",
        qa_suggester=c["qa_suggester"],
        registry=c["registry"],
        country_lang=c["country_lang"],
        lang_priority=language,
    )


def _translate(db, qid: str, language: str) -> dict:
    """懒翻译本体:单件单语言从 en 段纯翻译(补语种原语)。测试 monkeypatch 此处。"""
    from app.services.enrichment.backfill import translate_object_language
    from app.services.enrichment.factory import build_translator

    o = db.query(MuseumObject).filter_by(qid=qid).one()
    out = translate_object_language(
        db,
        o,
        language,
        build_translator("translate"),
    )
    db.commit()
    return out


def _tag_lazy_rows(db, obj: MuseumObject, since, source=LAZY_SOURCE) -> None:
    """把本次懒任务写的段标成 LAZY_SOURCE(日上限只数这些)。

    ponytail: 按「该件 + 本次开始后生成」圈行,不往写入咽喉里穿参数;
    同一件恰好同时被批量写入会多计几段,只会让闸更早停,方向安全。"""
    from app.models.content import ObjectContentSection

    db.query(ObjectContentSection).filter(
        ObjectContentSection.object_id == obj.id,
        ObjectContentSection.generated_at >= since,
    ).update({"source": source}, synchronize_session=False)
    db.commit()


def _run_locked(
    qid: str,
    work,
    label: str,
    *,
    session_factory=None,
    close=True,
    exempt=False,
    track=False,
    lang=None,
) -> None:
    """后台任务骨架:限并发跑 work(db),完成/失败均清锁(失败允许下次重试)。
    track=True(只有懒生成):记 lazy_started / lazy_finished(spec §7 T1/T3、§12 监控)。"""
    if session_factory is None:
        from app.core.database import SessionLocal

        session_factory = SessionLocal
    if not _SEM.acquire(blocking=False):
        # 并发满:放弃本次并清锁,下次访问重触发
        db = session_factory()
        try:
            o = db.query(MuseumObject).filter_by(qid=qid).one_or_none()
            if o:
                _clear_lock(db, o)
            _log_once(db, "lazy_slot_full", qid, kind=label, exempt=exempt)
        finally:
            if close:
                db.close()
        return
    run_id = uuid.uuid4().hex if track else None
    try:
        db = session_factory()
        try:
            if track:
                _log(
                    db,
                    "lazy_started",
                    qid=qid,
                    run_id=run_id,
                    running=_running_add(run_id),
                    exempt=exempt,
                )
            t0 = datetime.now(timezone.utc)
            m0 = time.monotonic()
            err = None
            try:
                out = work(db)
                logger.info("%s done: %s -> %s", label, qid, out)
            except Exception as e:
                err = e
                db.rollback()
                logger.exception("%s failed: %s", label, qid)
            o = db.query(MuseumObject).filter_by(qid=qid).one_or_none()
            if o:
                _tag_lazy_rows(db, o, t0)  # 失败前已落库的段也是花掉的钱,照样计
                _clear_lock(db, o)
            if track:
                try:  # 埋点绝不破坏业务:抛出去会让后面的补语言不跑
                    _log_finished(
                        db, o, run_id, lang, err, time.monotonic() - m0, exempt
                    )
                except Exception:
                    logger.warning("lazy_finished log failed: %s", qid, exc_info=True)
        finally:
            if close:
                db.close()
    finally:
        if track:
            _running_done(run_id)  # BaseException 时也要退出计数
        _SEM.release()


def _log(db, name, **props):
    from app.services.event_log import log_event

    log_event(db, name, **props)


def _log_once(db, name, qid, redis=None, **props):
    """同一件 10 分钟内只记一次(App 每 4 秒轮询会反复撞名额)。
    去重靠 Redis:Redis 为 None 或报错时不记,不能每 4 秒往库里写一行。"""
    r = redis if redis is not None else _redis()
    if r is None:
        return
    try:
        if not r.set(f"ops:once:{name}:{qid}", 1, nx=True, ex=600):
            return
    except Exception:
        return
    _log(db, name, qid=qid, **props)


_RUNNING_KEY = "ops:lazy_running"
_RUNNING_TTL_S = 900  # 被部署杀掉的进程漏掉的 ZREM,15 分钟后不再计入(B7)


def _running_add(run_id) -> int | None:
    """全站同时在生成的件数(含自己);Redis 不可用或报错 → None。"""
    try:
        r = _redis()
        if r is None:
            return None
        now = time.time()
        r.zadd(_RUNNING_KEY, {run_id: now})
        r.zremrangebyscore(_RUNNING_KEY, "-inf", now - _RUNNING_TTL_S)
        return int(r.zcard(_RUNNING_KEY))
    except Exception:
        return None


def _running_done(run_id) -> None:
    try:
        r = _redis()
        if r is not None:
            r.zrem(_RUNNING_KEY, run_id)
    except Exception:
        pass


def _error_kind(exc: BaseException) -> str:
    """失败类别(spec §3.1):超时、连接错误、429、5xx = transient,其余 internal。
    沿 __cause__/__context__ 往上找(pipeline 常把上游异常包一层)。阶段 4 的 error_kind 复用。"""
    import anthropic
    import httpx
    import openai
    import requests

    transient = (
        TimeoutError,
        ConnectionError,
        openai.APITimeoutError,
        openai.APIConnectionError,
        anthropic.APITimeoutError,
        anthropic.APIConnectionError,
        requests.exceptions.Timeout,
        requests.exceptions.ConnectionError,
        httpx.TimeoutException,
        httpx.NetworkError,
    )
    seen = set()
    e = exc
    while e is not None and id(e) not in seen:
        seen.add(id(e))
        code = getattr(e, "status_code", None)
        if isinstance(e, transient) or (
            isinstance(code, int) and (code == 429 or code >= 500)
        ):
            return "transient"
        e = e.__cause__ or e.__context__
    return "internal"


def _log_finished(db, o, run_id, lang, err, dur_s, exempt) -> None:
    """lazy_finished:pub/held = 这一件按语言的已发布 / needs_review 段数(懒生成只在 stub 上,
    全部段就是这次写的)。ok 还要求请求语言至少有一行段(R14:翻译异常会被 pipeline 吞掉)。"""
    from sqlalchemy import func

    from app.models.content import ObjectContentSection

    pub, held = {}, {}
    if o is not None:
        rows = (
            db.query(
                ObjectContentSection.language,
                ObjectContentSection.status,
                func.count(),
            )
            .filter(ObjectContentSection.object_id == o.id)
            .group_by(ObjectContentSection.language, ObjectContentSection.status)
            .all()
        )
        for lg, st, n in rows:
            if st == "published":
                pub[lg] = n
            elif st == "needs_review":
                held[lg] = n
    # empty(材料太薄,宁缺毋滥)是设计内结果,不看请求语言有没有段(Fable 终审 I2)
    empty = o is not None and o.content_status == "empty"
    has_lang = empty or lang in (None, "en") or bool(pub.get(lang) or held.get(lang))
    _log(
        db,
        "lazy_finished",
        qid=o.qid if o is not None else None,
        run_id=run_id,
        lang=lang,
        ok=err is None and has_lang,
        err_kind=_error_kind(err) if err is not None else None,
        dur_s=round(dur_s, 1),
        pub=pub,
        held=held,
        empty=empty,
        exempt=exempt,
    )


def run_lazy_generation(
    qid: str,
    language: str | None = None,
    exempt=False,
    *,
    session_factory=None,
    close=True,
) -> None:
    """stub 首访 → 生成英语轴心 + 请求语言;完成后补语言阶段补齐该馆其余语言
    (此时 _SEM 与 lazy_lock_at 都已释放,首屏和请求者自己的语言不受影响)。"""
    _run_locked(
        qid,
        lambda db: _generate(db, qid, language),
        "lazy generation",
        session_factory=session_factory,
        close=close,
        exempt=exempt,
        track=True,
        lang=language,
    )
    _run_fanout(qid, exempt, session_factory=session_factory, close=close)


def _museum_languages(db, obj: MuseumObject) -> list[str]:
    """该馆配置的语言集(museums.yaml 馆级覆盖,否则全局默认)——不写死语言个数。"""
    from app.models.museum import Museum
    from app.services.enrichment.catalog import MuseumCatalog
    from app.services.enrichment.factory import CATALOG_PATH
    from app.services.enrichment.lang_config import resolve_languages

    slug = db.query(Museum.slug).filter_by(id=obj.museum_id).scalar()
    return resolve_languages(MuseumCatalog.from_file(CATALOG_PATH).get(slug).languages)


def _fanout_langs(db, obj: MuseumObject, langs) -> list[str]:
    """要补的语言 = 配置语言集里这件还有 en 段/问答**没有已发布版本**的(en 轴心除外)。
    含半途失败(只有部分段)和被闸挡成 needs_review 的语言:补语言一件只跑一次(生成后/
    中断后恢复),重试的成本有界;按请求懒翻译的判据(_has_missing_section)仍把 needs_review
    算有,不在这里改。幂等:全发布后返回 []。"""
    from app.models.content import ObjectContentSection as S
    from app.models.content import ObjectSuggestedQuestion as Q

    def _pub(model, col, lang):
        return {
            c
            for (c,) in db.query(col).filter(
                model.object_id == obj.id,
                model.language == lang,
                model.status == "published",
                model.body.isnot(None) if model is S else model.answer.isnot(None),
            )
        }

    en_secs = _pub(S, S.section_code, "en")
    en_has_qa = bool(_pub(Q, Q.id, "en"))
    return [
        lang
        for lang in langs
        if lang != "en"
        and (
            en_secs - _pub(S, S.section_code, lang)
            or (en_has_qa and not _pub(Q, Q.id, lang))
        )
    ]


def _fanout(
    db,
    qid: str,
    *,
    langs=None,
    translator=None,
    session_factory=None,
    close=True,
    executor=None,
    redis=None,
    exempt=False,
) -> dict:
    """补语言阶段(spec 2026-10-17):懒生成完成后,把该馆其余语言的段/问答/作者 bio 补齐。
    不占 _SEM 和 lazy_lock_at;按语言的进行中标记见 fanout_pending。
    前置条件不满足(未 ready / 无 en / 无可补语言 / 自己的日上限 / 名额满)→ 返回 {},
    其余语言回到按请求懒翻译。测试注入 langs/translator/session_factory/executor/redis。"""
    o = db.query(MuseumObject).filter_by(qid=qid).one_or_none()
    if o is None or o.content_status != "ready" or not _has_published(db, o.id, "en"):
        return {}
    if (o.attributes or {}).get("lazy_fanout") and not fanout_stale(o):
        return {}  # 另一路补语言正在跑(并发的恢复请求);标记过期才接手
    remaining = _fanout_langs(
        db, o, langs if langs is not None else _museum_languages(db, o)
    )
    if not remaining:
        return {}
    if daily_budget_exhausted(db, _FANOUT_DAILY_SECTION_CAP, FANOUT_SOURCE):
        logger.warning("lazy fanout: 当日补语言预算用尽,跳过 qid=%s", qid)
        return {}
    if not _FANOUT_SEM.acquire(blocking=False):
        logger.info("lazy fanout: 名额已满,跳过 qid=%s", qid)
        _log_once(db, "lazy_fanout_slot_full", qid, redis=redis, exempt=exempt)
        return {}
    # acquire 后紧跟 try:之后任何一步抛异常都要还名额、清标记
    t0 = datetime.now(timezone.utc)
    out: dict = {}
    try:
        pending = list(remaining)
        # 先写标记再做其它初始化:首轮生成已清 lazy_lock_at,这之间别的语言用户打开会
        # 另起一路懒翻译。标记越早写,这个窗口越小(剩几条查询的时长,见 Ruling)。
        _set_fanout(db, o, pending)
        from app.services.enrichment.backfill import (
            artist_bio_en,
            fill_artist_bio,
            translate_object_language,
        )

        if translator is None:
            from app.services.enrichment.factory import build_translator

            translator = build_translator("translate")
        if session_factory is None:
            from app.core.database import guarded_sessionmaker

            # 带音频损失闸(纪律 37);绑同一个 engine,同 backfill_languages
            session_factory = guarded_sessionmaker(bind=db.get_bind())
        if redis is None:
            redis = _redis()
        bio_en, bio_have = artist_bio_en(db, o)
        oid = o.id

        def _one(lang):
            s = session_factory()  # 线程内独立 session:session 非线程安全
            try:
                c = translate_object_language(
                    s, s.get(MuseumObject, oid), lang, translator, include_bio=False
                )
                # 判官有随机性(同一段重试多半能过):被挡的段/问答再试一次,仅此一次
                for k, v in translate_object_language(
                    s, s.get(MuseumObject, oid), lang, translator, include_bio=False
                ).items():
                    c[k] += v
                s.commit()  # 保险:persist_* 已逐段提交,这里通常是空操作
            finally:
                if close:
                    s.close()
            # 作者 bio 只在线程里**翻**(并行,原先主线程串行 8 门约 33 秒);
            # 写由主线程做:bio 是跨馆共享行、整 JSON 覆盖写,线程里写会互相覆盖
            bio = None
            if bio_en and lang not in bio_have:
                try:
                    bio = translator.translate_section(bio_en, lang)
                except Exception:
                    logger.warning("lazy fanout bio failed: %s/%s", qid, lang)
            return c, bio

        queue = list(remaining)

        def _next():
            # 有人在等的语言插队;否则按原顺序
            want = _fanout_wanted(qid, redis)
            return queue.pop(next((i for i, x in enumerate(queue) if x in want), 0))

        pool = executor or ThreadPoolExecutor(max_workers=_FANOUT_WORKERS)
        running: dict = {}
        try:
            # 只把空闲线程数那么多门交给线程池,其余留在 queue:每空出一个才挑下一门,
            # 这样补到一半有人打开的语言也能插队
            while queue or running:
                while queue and len(running) < _FANOUT_WORKERS:
                    lang = _next()
                    running[pool.submit(_one, lang)] = lang
                done, _ = wait(running, return_when=FIRST_COMPLETED)
                for f in done:
                    lang = running.pop(f)
                    try:
                        c, bio = f.result()
                        out[lang] = c
                        if bio and fill_artist_bio(
                            db, o, lang, translator, refresh=True, text=bio
                        ):
                            c["bios"] = 1
                            db.commit()
                    except Exception:
                        logger.exception("lazy fanout failed: %s/%s", qid, lang)
                    pending.remove(lang)
                    # 每完成一门:打来源标签(进程被杀也已计入补语言日上限)+ 心跳,
                    # 这门语言的 generating 随之转 false
                    _tag_lazy_rows(db, o, t0, FANOUT_SOURCE)
                    _set_fanout(db, o, pending)
        finally:
            # BaseException(如进程关闭时的 SystemExit;web 进程音频闸只记账不拦,AudioLossBlocked
            # 只在脚本直接调用时可能出现)从 result() 冒出来时,别的语言还在跑或排队:
            # 取消排队的、等在跑的结束,**之后**才清标记还名额 —— 否则孤儿线程在标记清掉后
            # 继续写,generating 提前转 false、懒翻译重复点火(独立审查实测)
            pool.shutdown(wait=True, cancel_futures=True)
    finally:
        try:
            db.rollback()  # 之前的写都已提交;BaseException 后会话可能处于失败态
            _tag_lazy_rows(db, o, t0, FANOUT_SOURCE)
            _clear_fanout(db, o)
        finally:
            _FANOUT_SEM.release()
            try:
                if redis is not None:
                    redis.delete(_want_key(qid))
            except Exception:
                pass
    return out


def _run_fanout(qid: str, exempt=False, *, session_factory=None, close=True) -> None:
    """补语言后台骨架:自带会话,失败只记日志(其余语言回到按请求懒翻译)。"""
    if session_factory is None:
        from app.core.database import SessionLocal

        session_factory = SessionLocal
    db = session_factory()
    try:
        out = _fanout(db, qid, exempt=exempt)
        if out:
            logger.info("lazy fanout done: %s -> %s", qid, out)
    except Exception:
        db.rollback()
        logger.exception("lazy fanout failed: %s", qid)
    finally:
        if close:
            db.close()


def run_lazy_translation(
    qid: str, language: str, exempt=False, *, session_factory=None, close=True
) -> None:
    """ready 但请求语言缺 → 只翻这一门语言(数十秒,费用分钱级)。"""
    _run_locked(
        qid,
        lambda db: _translate(db, qid, language),
        "lazy translation",
        session_factory=session_factory,
        close=close,
        exempt=exempt,
    )


def run_lazy_images(qid: str, *, session_factory=None, close=True) -> None:
    """懒补漏(spec 图像自存):单件物化缺图。不占内容锁——图物化与内容生成可并行,
    撞了最多重复下载一张(幂等)。批量预物化为主,此钩子只兜运维疏漏/新进目录。"""
    if session_factory is None:
        from app.core.database import SessionLocal

        session_factory = SessionLocal
    db = session_factory()
    try:
        o = db.query(MuseumObject).filter_by(qid=qid).one_or_none()
        if o is not None:
            from app.services.enrichment.materializer import (
                materialize_object_images,
            )

            out = materialize_object_images(db, o)
            db.commit()
            logger.info("lazy images done: %s -> %s", qid, out)
    except Exception:
        db.rollback()
        logger.exception("lazy images failed: %s", qid)
    finally:
        if close:
            db.close()


def _has_missing_images(db, object_id) -> bool:
    from app.models.museum_object import ObjectImage

    return (
        db.query(ObjectImage)
        .filter(
            ObjectImage.object_id == object_id,
            ObjectImage.image_key.is_(None),
            ObjectImage.source_url.isnot(None),
        )
        .first()
        is not None
    )


def _has_published(db, object_id, lang) -> bool:
    from app.models.content import ObjectContentSection

    return (
        db.query(ObjectContentSection)
        .filter(
            ObjectContentSection.object_id == object_id,
            ObjectContentSection.language == lang,
            ObjectContentSection.status == "published",
            ObjectContentSection.body.isnot(None),
        )
        .first()
        is not None
    )


def _has_missing_section(db, object_id, lang) -> bool:
    """en 已发布的段里,有该语言**一行都没有**的(任何状态都算有)。
    取代原「该语言有任一段就不再触发」:那个判据下,半途失败(有 guide、缺深度段)的语言
    永远补不齐,补语言阶段会把这种半成品放大(spec 2026-10-17 §七)。
    needs_review 也算有 → 翻不过闸的段不会被反复点火烧钱。"""
    from app.models.content import ObjectContentSection as S

    en = {
        c
        for (c,) in db.query(S.section_code).filter(
            S.object_id == object_id,
            S.language == "en",
            S.status == "published",
            S.body.isnot(None),
        )
    }
    have = {
        c
        for (c,) in db.query(S.section_code).filter(
            S.object_id == object_id, S.language == lang
        )
    }
    return bool(en - have)


def daily_budget_exhausted(
    db, cap: int = _LAZY_DAILY_SECTION_CAP, source: str = LAZY_SOURCE
) -> bool:
    """今天已生成的段数是否已达上限。**这是钱包止损，不是权限检查。**

    身份闸（端点侧：匿名不点火）把"任何人无限刷"变成"注册一个号就能刷"——
    可追溯、可封号，但**不会自动停**。按 `_SEM(2)` × 2 worker × 每次 30-60s 估，
    一个脚本化账号约 5 天能跑完全库。这道闸钉住的是**最坏一天能花多少钱**，
    与调用者是谁无关 —— 正是身份闸覆盖不到的那一半。

    只数懒任务写的段(`source == LAZY_SOURCE`)。原先刻意不分来源、管当天总花费,
    代价是批量跑的那天用户点开新语言全被跳过 —— 2026-09-28 实际发生(见 LAZY_SOURCE)。
    批量是运营者看着跑的,不需要这道止损。
    source=FANOUT_SOURCE 时管补语言自己的日上限(spec 2026-10-17 §4.4)。
    """
    from app.models.content import ObjectContentSection

    start = datetime.now(timezone.utc).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    return (
        db.query(ObjectContentSection)
        .filter(
            ObjectContentSection.generated_at >= start,
            ObjectContentSection.source == source,
        )
        .count()
        >= cap
    )


def _redis():
    """复用识别缓存的 Redis 单例(自带连接失败冷却,Redis 挂了不会每次请求等超时)。"""
    from app.services.recognition.service import _get_redis

    return _get_redis()


def _today() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d")


def _alert_fail_open() -> None:
    ops_alert.alert_throttled(
        "lazy-caps-redis",
        "[GoMuseum] Redis 不可用:懒生成每账号/每 IP 额度已放行",
        "懒生成额度检查连不上 Redis,正按 fail-open 放行,只剩全站上限兜底。\n"
        "去查 Redis 容器;本进程 6 小时内不再重复发。",
    )


def _charge(user_id, ip, weight: int, redis=None, item=None, guest=True) -> str | None:
    """按账号、按 IP 扣当日额度。None=放行;"user"/"ip"=该层超限(已全部回滚)。

    item(如 "gen:Q1"/"tr:Q1:de"):同一人同一动作当天只扣一次。生成名额满时后台放弃并清锁,
    App 每 4s 轮询又点火一次;按次扣的话 ~80s 就把用户当天额度烧光而一个字没生成(10-20 复现)。
    ponytail: 失败后当天重试也不再扣,只靠全站上限兜底;失败率真高了再按结果退额度。

    先 INCRBY 再判断:INCRBY 原子,两个 worker 并发也不会越线(先查后加会)。
    超限就把本次加上的全部退回,被拒的请求不占额度。
    Redis 不可用 → 放行(fail open):全站上限在 DB,照样兜底;反过来 Redis 一抖全站懒生成就停了。
    guest=False(正式账号):IP 层改用 lazy:ipr:、上限 CAP_PER_IP_REGISTERED;身份不明按游客。
    """
    ip_layer = ("ip", ip, CAP_PER_IP) if guest else ("ipr", ip, CAP_PER_IP_REGISTERED)
    layers = [
        (name, f"lazy:{name}:{ident}:{_today()}", cap)
        for name, ident, cap in (("u", user_id, CAP_PER_USER), ip_layer)
        if ident
    ]
    if not layers:
        return None
    r = redis if redis is not None else _redis()
    if r is None:
        logger.error(
            "lazy caps: redis unavailable, allowing (global cap still applies)"
        )
        _alert_fail_open()
        return None
    paid = f"lazy:paid:{user_id or ip}:{item}:{_today()}" if item else None
    try:
        if paid and not r.set(paid, 1, nx=True, ex=_CAP_TTL_S):
            return None  # 今天已为这件付过
        pipe = r.pipeline()
        for _, key, _cap in layers:
            pipe.incrby(key, weight)
            # 每次都设:键里带日期,重复设无害,不会漏设成永不过期
            pipe.expire(key, _CAP_TTL_S)
        used = pipe.execute()[0::2]
        over = [name for (name, _, cap), u in zip(layers, used) if int(u) > cap]
        if not over:
            return None
    except Exception:
        logger.exception("lazy caps: redis error, allowing (global cap still applies)")
        _alert_fail_open()
        return None
    layer = "user" if "u" in over else "ip"
    logger.warning(
        "lazy: cap hit layer=%s user=%s ip=%s used=%s", layer, user_id, ip, used
    )
    # 已知超限:退额度失败也照样拒绝。退不回去只会让这些键多计一次 weight,
    # 当天提前一点被拦;键带 UTC 日期,次日自然换新键,不会长期卡住。
    try:
        pipe = r.pipeline()
        for _, key, _cap in layers:
            pipe.decrby(key, weight)
        if paid:
            pipe.delete(paid)  # 被拒不算付过
        pipe.execute()
    except Exception:
        logger.exception("lazy caps: rollback failed, keys over-counted by %s", weight)
    return layer


def _log_cap_hit(db, qid, layer, is_guest, kind):
    """额度用尽埋点(spec §7 T4)。exempt 账号不扣额度,所以这里恒为 False。"""
    from app.services.event_log import log_event

    log_event(
        db,
        "lazy_cap_hit",
        qid=qid,
        layer=layer,
        tier="guest" if is_guest else "registered",
        kind=kind,
        exempt=False,
    )


def imageless_stub(db, obj) -> bool:
    """无图 stub 不点火(方案 B 2026-10-11):列表/搜索/识别都不给无图件,用户本就到不了;
    生成了也没图可看、外观描写还会是编的。口径同探索列表(has_image_clause)。"""
    from app.services.must_see import has_image_clause

    if obj.content_status != "stub":
        return False
    return (
        db.query(MuseumObject.id)
        .filter(MuseumObject.id == obj.id, has_image_clause())
        .first()
        is None
    )


def maybe_trigger(
    db,
    qid: str,
    *,
    schedule,
    environment=None,
    language=None,
    user_id=None,
    ip=None,
    exempt=False,
    redis=None,
    is_guest=True,
) -> str | None:
    """content 端点接线(拿到锁才调度,其余静默)。返回不生成的原因,端点透传给 App:
    "daily_cap"=当日预算用尽(App 提示明天再来);"no_image"=无图 stub 不生成;其余 None。
    - stub → 懒生成(完整生成,请求语言优先);
    - ready 但请求语言缺已发布内容且有 en 轴心 → 懒翻译(只翻该语言);
    - empty 不动(无可接地材料,防循环烧钱)。
    只在部署环境生效(development/测试不触发:防误连库、误烧 LLM 费)。
    - user_id/ip:按账号/IP 扣当日额度(拿到锁后才扣,超了清锁返回 "daily_cap");
      exempt=运营预览账号,只受全站上限;is_guest 选 IP 层档位(见 _charge)。"""
    if environment is None:
        from app.core.config import settings

        environment = settings.ENVIRONMENT
    if environment not in ("staging", "production"):
        return
    o = db.query(MuseumObject).filter_by(qid=qid).one_or_none()
    if o is None:
        return
    if _has_missing_images(db, o.id):  # 懒补漏:缺图顺手补(独立于内容动作)
        schedule(run_lazy_images, qid)
    wants_generation = o.content_status == "stub"
    wants_translation = (
        o.content_status == "ready"
        and language
        and language != "en"
        and language not in fanout_pending(o)
        and _has_missing_section(db, o.id, language)
        and _has_published(db, o.id, "en")
    )
    if language and language != "en" and generating_for(o, language):
        record_fanout_want(qid, language, redis)  # 补语言阶段先补有人在等的语言
    if o.content_status == "ready" and fanout_stale(o) and not lock_active(o):
        schedule(_run_fanout, qid, exempt)  # 补语言进程中途死了(如部署重启):接着补
    if not (wants_generation or wants_translation):
        return
    if wants_generation and imageless_stub(db, o):
        return "no_image"  # 在额度检查之前:不扣方案 A 的额度
    # 预算检查放在这里而不是函数开头:它是一条 COUNT,而绝大多数请求打的是
    # 已 ready 的件、上面就返回了。放开头等于给每次详情页浏览加一次全表扫描。
    if daily_budget_exhausted(db):
        logger.warning(
            "lazy: 当日生成预算已用尽(cap=%s),跳过 qid=%s language=%s",
            _LAZY_DAILY_SECTION_CAP,
            qid,
            language,
        )
        return "daily_cap"
    if wants_generation:
        if try_acquire_lock(db, o):
            layer = not exempt and _charge(
                user_id, ip, WEIGHT_GENERATION, redis, f"gen:{qid}", is_guest
            )
            if layer:
                _clear_lock(db, o)
                _log_cap_hit(db, qid, layer, is_guest, "lazy generation")
                return "daily_cap"
            schedule(run_lazy_generation, qid, language, exempt)
        return
    if try_acquire_lock(db, o, require_status=("ready",)):
        layer = not exempt and _charge(
            user_id, ip, WEIGHT_TRANSLATION, redis, f"tr:{qid}:{language}", is_guest
        )
        if layer:
            _clear_lock(db, o)
            _log_cap_hit(db, qid, layer, is_guest, "lazy translation")
            return "daily_cap"
        schedule(run_lazy_translation, qid, language, exempt)
