"""从 DB 读馆藏并拼回与旧 museum_packs JSON 完全一致的形状（保接口兼容）。"""

from datetime import datetime, timezone

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.content import (
    CategorySection,
    ObjectContentSection,
    ObjectSuggestedQuestion,
    SectionType,
)
from app.models.museum import Museum
from app.models.museum_object import MuseumObject, ObjectImage
from app.services.enrichment.category_config import section_label
from app.services.storage import get_object_storage

_PACK_FIELDS = ("slug", "name_zh", "name_en", "city_zh", "city_en", "country")

_LEGACY_SOURCE = "Wikidata/Wikimedia Commons (public data)"


def list_museums(db: Session) -> list[dict]:
    rows = (
        db.query(Museum, func.count(MuseumObject.id).label("cnt"))
        .outerjoin(MuseumObject, MuseumObject.museum_id == Museum.id)
        .group_by(Museum.id)
        .order_by(Museum.slug)
        .all()
    )
    out = []
    for m, cnt in rows:
        row = {f: getattr(m, f) for f in _PACK_FIELDS}
        row["artwork_count"] = cnt
        out.append(row)
    return out


def get_museum_pack(db: Session, slug: str) -> dict | None:
    m = db.query(Museum).filter_by(slug=slug).one_or_none()
    if not m:
        return None
    objs = (
        db.query(MuseumObject)
        .filter_by(museum_id=m.id)
        .order_by(MuseumObject.popularity.desc())
        .all()
    )
    obj_ids = [o.id for o in objs]
    # Batch-load all primary images in one query
    images_by_obj: dict[int, ObjectImage] = {}
    if obj_ids:
        for img in (
            db.query(ObjectImage)
            .filter(ObjectImage.object_id.in_(obj_ids), ObjectImage.role == "primary")
            .all()
        ):
            images_by_obj[img.object_id] = img

    storage = get_object_storage()

    def _resolve_image(obj_id, fallback_src):
        img = images_by_obj.get(obj_id)
        if img and img.image_key:
            return storage.public_url(img.image_key)
        return (img.source_url if img else None) or fallback_src

    artworks = [
        {
            "qid": o.qid,
            # title_zh 永不为 null：富化数据常缺中文标题，回退 title_en→qid，
            # 否则前端 `title_zh as String` 强转会崩（馆藏列表整页加载失败）。
            "title_zh": o.title_zh or o.title_en or o.qid,
            "title_en": o.title_en,
            "artist_zh": o.artist_zh,
            "artist_en": o.artist_en,
            "year": o.year,
            "period_zh": o.period_zh,
            "period_en": o.period_en,
            "image": _resolve_image(o.id, None),
            "popularity": o.popularity,
        }
        for o in objs
    ]
    pack = {f: getattr(m, f) for f in _PACK_FIELDS}
    pack.update(
        {
            "qid": m.qid,
            "source": _LEGACY_SOURCE,
            "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "artwork_count": len(artworks),
            "artworks": artworks,
        }
    )
    return pack


def get_object_content(db: Session, slug: str, qid: str, language: str) -> dict | None:
    obj = db.query(MuseumObject).filter_by(qid=qid).one_or_none()
    if not obj:
        return None
    # Validate that the object belongs to the museum identified by slug
    museum = db.query(Museum).filter_by(id=obj.museum_id).one_or_none()
    if not museum or museum.slug != slug:
        return None
    mapping = (
        db.query(CategorySection, SectionType)
        .join(SectionType, CategorySection.section_code == SectionType.code)
        .filter(CategorySection.category == obj.category)
        .order_by(CategorySection.sort_order)
        .all()
    )
    bodies = {
        c.section_code: c
        for c in db.query(ObjectContentSection)
        .filter_by(object_id=obj.id, language=language)
        .all()
    }
    storage = get_object_storage()
    tabs = []
    for cs, st in mapping:
        row = bodies.get(cs.section_code)
        tabs.append(
            {
                "section_code": cs.section_code,
                "label": section_label(cs.section_code, language),
                "icon": st.icon,
                "body": row.body if row else None,
                "audio_url": (
                    storage.public_url(row.audio_key) if row and row.audio_key else None
                ),
            }
        )
    suggested = [
        {"question": q.question, "answer": q.answer}
        for q in db.query(ObjectSuggestedQuestion)
        .filter_by(object_id=obj.id, language=language, status="published")
        .order_by(ObjectSuggestedQuestion.sort)
        .all()
    ]
    return {
        "qid": qid,
        "category": obj.category,
        "language": language,
        "tabs": tabs,
        "suggested_questions": suggested,
    }
