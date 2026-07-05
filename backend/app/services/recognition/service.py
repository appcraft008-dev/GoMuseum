"""识别编排:校验/哈希 → 缓存 → vision(引擎位,P2 换 CLIP) → 目录匹配 → 三档分流。
R1 接地:响应里的身份只可能来自目录命中;不中诚实 unrecognized + 记需求(R5)。
spec docs/superpowers/specs/2026-07-03-recognition-design.md。"""

from __future__ import annotations

import json
import logging

from app.models.artist import Artist
from app.models.museum import Museum
from app.models.museum_object import MuseumObject, ObjectImage
from app.services.museum_repo import _resolve_name, _sized
from app.services.recognition.demands import record_demand
from app.services.recognition.matcher import HIGH, LOW, build_index, match
from app.services.recognition.vision import identify

logger = logging.getLogger(__name__)

_CACHE_TTL_MATCH = 30 * 86400  # 命中稳定:30天
_CACHE_TTL_MISS = 86400  # 未收录:目录会生长,只缓 1 天


def _cache_key(slug: str, sha: str, language: str) -> str:
    return f"recog2:{slug}:{language}:{sha}"


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
    return {
        "qid": o.qid,
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


def recognize(
    db,
    slug: str,
    image_bytes: bytes,
    *,
    language: str = "zh",
    mode: str = "artwork",
    identify_fn=None,
    redis=None,
) -> dict | None:
    """拍照识别。未知馆 → None。响应形状见 spec(outcome/reason 机器码)。"""
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

    identify_fn = identify_fn or identify
    vis = identify_fn(ImageService.to_base64(image_bytes), mode=mode)
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
        from app.services.storage import get_object_storage

        storage = get_object_storage()
        results = match(build_index(db, museum.id), queries, label_lines, artist_hints)
        top = results[0] if results else None
        if top and top[1] >= HIGH:
            o = db.query(MuseumObject).filter_by(qid=top[0]).one()
            out["outcome"] = "match"
            out["match"] = {
                **_summary(db, storage, o, language),
                "confidence": round(top[1], 3),
            }
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

    if out["outcome"] == "unrecognized":
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
    slug: str,
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
