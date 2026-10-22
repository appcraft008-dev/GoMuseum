"""网页试听(spec 2026-10-22-website-v1 §6):每馆每语言自动选 ≤5 件。

只有这几件的已录音频能经 `/w/audio` 拿到;别的作品一个字节都不给(音频是收费核心资产)。
只读 audio_key,从不合成、从不点火 —— 没录的段就是没有。
"""

import time

from sqlalchemy import func

from app.models.artist import Artist
from app.models.content import ObjectContentSection, ObjectSuggestedQuestion
from app.models.museum import Museum
from app.models.museum_object import MuseumObject
from app.services.must_see import MUST_SEE, has_image_clause

TRIAL_LIMIT = 5
_TTL = 600
# ponytail: 进程内 10 分钟缓存,每 worker 一份;试听名单换了最多晚 10 分钟生效
_cache: dict = {}


def _published(lang):
    return (
        ObjectContentSection.language == lang,
        ObjectContentSection.status == "published",
        ObjectContentSection.audio_key.isnot(None),
    )


def trial_qids(db, museum: Museum, language: str) -> list[str]:
    key = (museum.id, language)
    hit = _cache.get(key)
    if hit and time.monotonic() - hit[0] < _TTL:
        return hit[1]
    got = _pick(db, museum, language)
    _cache[key] = (time.monotonic(), got)
    return got


def _pick(db, museum: Museum, language: str) -> list[str]:
    q = (
        db.query(MuseumObject)
        .join(ObjectContentSection, ObjectContentSection.object_id == MuseumObject.id)
        .filter(
            MuseumObject.museum_id == museum.id,
            ObjectContentSection.section_code == "guide",
            *_published(language),
            has_image_clause(),
        )
    )
    listed = MUST_SEE.get(museum.slug) or []
    if listed:
        q = q.filter(MuseumObject.qid.in_(listed))
    objs = q.all()
    if not objs:
        return []
    ids = [o.id for o in objs]
    sec = dict(
        db.query(ObjectContentSection.object_id, func.count())
        .filter(ObjectContentSection.object_id.in_(ids), *_published(language))
        .group_by(ObjectContentSection.object_id)
        .all()
    )
    qa = dict(
        db.query(ObjectSuggestedQuestion.object_id, func.count())
        .filter(
            ObjectSuggestedQuestion.object_id.in_(ids),
            ObjectSuggestedQuestion.language == language,
            ObjectSuggestedQuestion.status == "published",
            ObjectSuggestedQuestion.audio_key.isnot(None),
        )
        .group_by(ObjectSuggestedQuestion.object_id)
        .all()
    )
    aqids = {(o.attributes or {}).get("artist_qid") for o in objs} - {None}
    bio = {
        a.qid
        for a in db.query(Artist).filter(Artist.qid.in_(list(aqids)))
        if (a.bio_audio or {}).get(language)
    }
    order = {q: i for i, q in enumerate(listed)}

    def score(o):
        n = sec.get(o.id, 0) + qa.get(o.id, 0)
        n += 1 if (o.attributes or {}).get("artist_qid") in bio else 0
        return (-n, order.get(o.qid, 0), -(o.popularity or 0), str(o.id))

    return [o.qid for o in sorted(objs, key=score)[:TRIAL_LIMIT]]


def trial_parts(db, obj: MuseumObject, language: str) -> dict[str, str]:
    """part → audio_key,只含真有音频的段。part:guide / 深度段 code / artist_bio / qa-{sort}。"""
    parts = {
        code: key
        for code, key in db.query(
            ObjectContentSection.section_code, ObjectContentSection.audio_key
        ).filter(ObjectContentSection.object_id == obj.id, *_published(language))
    }
    aq = (obj.attributes or {}).get("artist_qid")
    if aq:
        art = db.query(Artist).filter_by(qid=aq).one_or_none()
        key = ((art.bio_audio or {}) if art else {}).get(language)
        if key:
            parts["artist_bio"] = key
    for sort, key in db.query(
        ObjectSuggestedQuestion.sort, ObjectSuggestedQuestion.audio_key
    ).filter(
        ObjectSuggestedQuestion.object_id == obj.id,
        ObjectSuggestedQuestion.language == language,
        ObjectSuggestedQuestion.status == "published",
        ObjectSuggestedQuestion.audio_key.isnot(None),
    ):
        parts[f"qa-{sort}"] = key
    return parts
