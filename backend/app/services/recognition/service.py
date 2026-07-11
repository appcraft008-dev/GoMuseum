"""识别编排:校验/哈希 → 缓存 → vision(引擎位,P2 换 CLIP) → 目录匹配 → 三档分流。
R1 接地:响应里的身份只可能来自目录命中;不中诚实 unrecognized + 记需求(R5)。
spec docs/superpowers/specs/2026-07-03-recognition-design.md。"""

from __future__ import annotations

import io
import json
import logging

from app.core.config import settings
from app.models.artist import Artist
from app.models.museum import Museum
from app.models.museum_object import MuseumObject, ObjectImage
from app.services.museum_repo import _resolve_name, _sized
from app.services.recognition.demands import record_demand
from app.services.recognition.matcher import LOW, build_index, match
from app.services.recognition.vector_index import query_index
from app.services.recognition.vision import identify

logger = logging.getLogger(__name__)

_CACHE_TTL_MATCH = 30 * 86400  # 命中稳定:30天
_CACHE_TTL_MISS = 86400  # 未收录:目录会生长,只缓 1 天


def _cache_key(slug: str | None, sha: str, language: str) -> str:
    return f"recog3:{slug or 'global'}:{language}:{sha}"


def _default_embed(image_bytes: bytes):
    """默认 embed_fn:包装 DINOv2 引擎。引擎不可用/解码或推理异常 → None(编排层走 GPT 兜底)。
    validate_image 的 PIL verify() 不解码像素——截断 JPEG 会过校验、在此处才爆,不许炸出去。"""
    from PIL import Image

    from app.services.recognition.embedder import get_embedder

    engine = get_embedder()
    if engine is None:
        return None
    try:
        return engine.embed(Image.open(io.BytesIO(image_bytes)))
    except Exception:
        logger.exception("embed failed, falling back to GPT chain")
        return None


def _default_embed_crops(image_bytes: bytes):
    """默认 embed_crops_fn:裁剪金字塔批量 embedding。引擎不可用/异常 → None(编排层走 GPT 兜底)。"""
    from PIL import Image

    from app.services.recognition.embedder import crop_pyramid, get_embedder

    engine = get_embedder()
    if engine is None:
        return None
    try:
        img = Image.open(io.BytesIO(image_bytes))
        return engine.embed_batch(crop_pyramid(img))
    except Exception:
        logger.exception("embed_crops failed, falling back to GPT chain")
        return None


def _get_redis():
    try:
        from app.services.cache_service import get_cache_service

        return get_cache_service().redis_client
    except Exception:
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
    thumbnail = None
    if img and img.image_key:
        thumbnail = _sized(storage, img.image_key, "thumb")
    elif img:
        thumbnail = img.source_url
    mus = db.query(Museum).filter_by(id=o.museum_id).first()
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
    }


def _vector_out(db, storage, ranked: list, language: str) -> dict | None:
    """向量检索 [(qid,score)] → 输出 dict(match/candidates);top<LOW 或空 → None(触发下一档)。
    纯向量命中:未调 GPT,label_text/reason 恒 None。"""
    if not ranked:
        return None
    top_score = ranked[0][1]
    if top_score >= settings.RECOG_HIGH:
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
) -> dict | None:
    """拍照识别:DINOv2 向量前置(三档)→ miss 则 GPT+OCR 兜底。
    slug=None → 全局(不查馆、不过滤);slug 给了但馆不存在 → None(老语义)。
    响应形状见 spec(outcome/reason 机器码)。"""
    museum = None
    if slug is not None:
        museum = db.query(Museum).filter_by(slug=slug).one_or_none()
        if museum is None:
            return None
    from app.services.image_service import ImageService

    ImageService.validate_image(image_bytes)
    sha = ImageService.generate_hash(image_bytes)
    phash = ImageService.generate_perceptual_hash(image_bytes)

    redis = redis if redis is not None else _get_redis()
    ckey = _cache_key(slug, sha, language)
    if redis is not None:
        try:
            hit = redis.get(ckey)
            if hit:
                cached_out = json.loads(hit)
                cached_out["_billed"] = True  # 缓存命中:计费层据此不扣次
                return cached_out
        except Exception:
            pass  # 缓存不可用不阻断识别

    from app.services.storage import get_object_storage

    storage = get_object_storage()
    museum_id = museum.id if museum else None

    out = None
    vis = None
    # --- 向量前置(仅 artwork;label 纯转写直走 GPT 链) ---
    if mode == "artwork":
        vec = (embed_fn or _default_embed)(image_bytes)
        if vec is not None:
            vquery = vector_query_fn or query_index
            ranked = vquery(db, vec, museum_id)
            # 全景式拍法(画占画面小)的对症药——实测 0.509→0.847;怼拍照片不受影响(快路径)。
            # 全帧已 ≥ LOW → 不跑金字塔;否则裁剪重查,跨全帧+裁剪按 qid 取 MAX,重定档。
            if not ranked or ranked[0][1] < settings.RECOG_LOW:
                crops = (embed_crops_fn or _default_embed_crops)(image_bytes)
                if crops is not None:
                    agg = dict(ranked)
                    for cv in crops:
                        for qid, s in vquery(db, cv, museum_id):
                            if s > agg.get(qid, -2.0):
                                agg[qid] = s
                    ranked = sorted(agg.items(), key=lambda kv: -kv[1])
            out = _vector_out(db, storage, ranked, language)
            # 馆域调用不回退全局:老端点已部署 App 不读 museum 字段,跨馆命中会拿他馆
            # qid 撞 /{slug}/objects/{qid}/content 404 死胡同(前向兼容硬约束)。
            # 将来带馆提示的新调用方要全局回退时,加显式参数再开;slug=None 首查即全局。

    if out is None:  # --- GPT + OCR 兜底链(原样) ---
        from app.services.recognition.vision import _shrink

        identify_fn = identify_fn or identify
        vis = identify_fn(ImageService.to_base64(_shrink(image_bytes)), mode=mode)
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
            results = match(
                build_index(db, museum_id), queries, label_lines, artist_hints
            )
            top = results[0] if results else None
            # 文字链证据=名字对上≠就是这件(同名撞车 E2E 实证:自画像/The Bathers);
            # 直判只属于向量像素证据。将来 matcher 若回传"馆藏号命中"类型,可为 inv 命中恢复直判。
            if top and top[1] >= LOW:
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

    if redis is not None:
        try:
            ttl = _CACHE_TTL_MATCH if out["outcome"] == "match" else _CACHE_TTL_MISS
            redis.setex(ckey, ttl, json.dumps(out, ensure_ascii=False))
        except Exception:
            pass
    return out


class QuotaExceededError(Exception):
    """识别配额用尽(端点映射 402;缓存命中也拦——付费墙语义)。"""


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
) -> dict | None:
    """带配额的识别(计费规则,用户 2026-07-04 批准):
    match/candidates 扣 1;unrecognized 不扣(不为失败付费);缓存命中不扣(不重复扣);
    配额用尽 → QuotaExceededError(先于 GPT 调用,不烧钱)。"""
    from app.services.benefits_service import BenefitsService

    benefits = BenefitsService(db)
    access = benefits.check_access(user_id, device_id)
    if not access.get("has_access"):
        raise QuotaExceededError()
    out = recognize(
        db,
        slug,
        image_bytes,
        language=language,
        mode=mode,
        identify_fn=identify_fn,
        redis=redis,
    )
    if out is not None and out.get("outcome") in ("match", "candidates"):
        cached = out.pop("_billed", None)  # 缓存命中标记(见 recognize)
        if not cached:
            try:
                benefits.consume_recognition(user_id, device_id)
            except Exception:
                logger.exception("consume_recognition failed")
    else:
        if out is not None:
            out.pop("_billed", None)
    return out
