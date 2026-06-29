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

_CATEGORY_LABELS = {
    "painting": {"zh": "绘画", "en": "Painting", "fr": "Peinture"},
    "sculpture": {"zh": "雕塑", "en": "Sculpture", "fr": "Sculpture"},
    "photography": {"zh": "摄影", "en": "Photography", "fr": "Photographie"},
    "decorative_arts": {
        "zh": "装饰艺术",
        "en": "Decorative Arts",
        "fr": "Arts décoratifs",
    },
    "unknown": {"zh": "其他", "en": "Other", "fr": "Autre"},
}
_ALL_LABEL = {"zh": "全部", "en": "All", "fr": "Tout"}


def _category_label(code: str, lang: str) -> str:
    m = _CATEGORY_LABELS.get(code, {})
    return m.get(lang) or m.get("en") or code


def _pick(lang: str, zh, en, fr, fallback=""):
    """按语言选值，带回退链。zh→zh/en；fr→fr/en；其它→en/zh。"""
    if lang == "zh":
        return zh or en or fallback
    if lang == "fr":
        return fr or en or fallback
    return en or zh or fallback


def _split_hash(s):
    """Joconde 多值字段用 '#' 分隔 → list；空→[]。"""
    return [p.strip() for p in s.split("#") if p.strip()] if s else []


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


def get_museum_pack(db: Session, slug: str, language: str = "zh") -> dict | None:
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
    cat_rows = (
        db.query(MuseumObject.category, func.count())
        .filter_by(museum_id=m.id)
        .group_by(MuseumObject.category)
        .all()
    )
    total = sum(c for _, c in cat_rows)
    categories = [
        {"code": "all", "label": _ALL_LABEL.get(language, "全部"), "count": total}
    ] + [
        {"code": code, "label": _category_label(code, language), "count": cnt}
        for code, cnt in sorted(cat_rows, key=lambda x: -x[1])
    ]

    pack = {f: getattr(m, f) for f in _PACK_FIELDS}
    pack.update(
        {
            "qid": m.qid,
            "source": _LEGACY_SOURCE,
            "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "artwork_count": len(artworks),
            "categories": categories,
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
    attrs = obj.attributes or {}
    images = [
        {
            "url": storage.public_url(i.image_key) if i.image_key else i.source_url,
            "credit": i.credit,
        }
        for i in db.query(ObjectImage)
        .filter_by(object_id=obj.id)
        .order_by(ObjectImage.sort)
        .all()
        if i.image_key or i.source_url
    ]
    facts = {
        "artist": _pick(language, obj.artist_zh, obj.artist_en, attrs.get("artist_fr")),
        "date": obj.year,
        "medium": attrs.get("medium_fr"),
        "dimensions": attrs.get("dimensions"),
        "inventory": obj.inventory_number,
        "location": _pick(language, museum.name_zh, museum.name_en, museum.name_en),
        "provenance": attrs.get("provenance_fr"),
        "artist_life": None,  # ponytail: 未存作者生平，接 Wikidata 作者源后再补
        "exhibitions": _split_hash(attrs.get("exhibitions_fr")),
        "bibliography": _split_hash(attrs.get("bibliography_fr")),
    }
    guide_row = (
        db.query(ObjectContentSection)
        .filter_by(object_id=obj.id, language=language, section_code="guide")
        .one_or_none()
    )
    default_guide = (
        {
            "body": guide_row.body,
            "audio_url": (
                storage.public_url(guide_row.audio_key) if guide_row.audio_key else None
            ),
        }
        if guide_row and guide_row.body
        else None
    )
    return {
        "qid": qid,
        "category": obj.category,
        "language": language,
        "status": obj.content_status,
        "title": _pick(
            language, obj.title_zh, obj.title_en, attrs.get("title_fr"), qid
        ),
        "images": images,
        "facts": facts,
        "tabs": tabs,
        "default_guide": default_guide,
        "suggested_questions": suggested,
    }


def list_objects(
    db: Session,
    slug: str,
    *,
    language: str = "zh",
    category: str | None = None,
    sort: str = "popularity",
    limit: int = 50,
    offset: int = 0,
) -> dict | None:
    """分页藏品列表（供 A2/A3 列表页）。未知馆→None。纯元数据 + content_status。"""
    m = db.query(Museum).filter_by(slug=slug).one_or_none()
    if not m:
        return None
    q = db.query(MuseumObject).filter_by(museum_id=m.id)
    if category and category != "all":
        q = q.filter(MuseumObject.category == category)
    total = q.count()
    q = q.order_by(MuseumObject.popularity.desc())
    objs = q.limit(limit).offset(offset).all()

    obj_ids = [o.id for o in objs]
    images_by_obj: dict = {}
    if obj_ids:
        for img in (
            db.query(ObjectImage)
            .filter(ObjectImage.object_id.in_(obj_ids), ObjectImage.role == "primary")
            .all()
        ):
            images_by_obj[img.object_id] = img
    storage = get_object_storage()

    def _thumb(obj_id):
        img = images_by_obj.get(obj_id)
        if img and img.image_key:
            return storage.public_url(img.image_key)
        return img.source_url if img else None

    def _title(o):
        if language == "zh":
            return o.title_zh or o.title_en or o.qid
        if language == "fr":
            return (o.attributes or {}).get("title_fr") or o.title_en or o.qid
        return o.title_en or o.title_zh or o.qid

    def _artist(o):
        if language == "zh":
            return o.artist_zh or o.artist_en or ""
        if language == "fr":
            return (o.attributes or {}).get("artist_fr") or o.artist_en or ""
        return o.artist_en or o.artist_zh or ""

    items = [
        {
            "qid": o.qid,
            "title": _title(o),
            "artist": _artist(o),
            "year": o.year,
            "thumbnail": _thumb(o.id),
            "content_status": o.content_status,
        }
        for o in objs
    ]
    return {"items": items, "total": total, "limit": limit, "offset": offset}
