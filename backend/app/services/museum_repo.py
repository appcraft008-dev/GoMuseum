"""从 DB 读馆藏并拼回与旧 museum_packs JSON 完全一致的形状（保接口兼容）。"""

import re
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

# 通用分类法 8 大类(契约§收录策略),全馆共用;奥赛启用前 4 类。
# label 全 6 语(交接 2026-07-03-backend-category-label-i18n):固定小集合,静态表即可;缺译回退 en。
_CATEGORY_LABELS = {
    "painting": {
        "zh": "绘画",
        "en": "Painting",
        "fr": "Peinture",
        "de": "Malerei",
        "es": "Pintura",
        "it": "Dipinti",
    },
    "sculpture": {
        "zh": "雕塑",
        "en": "Sculpture",
        "fr": "Sculpture",
        "de": "Skulpturen",
        "es": "Escultura",
        "it": "Sculture",
    },
    "works_on_paper": {
        "zh": "纸上作品",
        "en": "Works on Paper",
        "fr": "Arts graphiques",
        "de": "Arbeiten auf Papier",
        "es": "Obra sobre papel",
        "it": "Opere su carta",
    },
    "photography": {
        "zh": "摄影",
        "en": "Photography",
        "fr": "Photographie",
        "de": "Fotografie",
        "es": "Fotografía",
        "it": "Fotografia",
    },
    "decorative_arts": {
        "zh": "装饰艺术",
        "en": "Decorative Arts",
        "fr": "Arts décoratifs",
        "de": "Kunstgewerbe",
        "es": "Artes decorativas",
        "it": "Arti decorative",
    },
    "textile": {
        "zh": "纺织",
        "en": "Textiles",
        "fr": "Textiles",
        "de": "Textilien",
        "es": "Textiles",
        "it": "Tessuti",
    },
    "artifact": {
        "zh": "文物器物",
        "en": "Artifacts",
        "fr": "Objets",
        "de": "Artefakte",
        "es": "Artefactos",
        "it": "Reperti",
    },
    "manuscript": {
        "zh": "手稿古籍",
        "en": "Manuscripts",
        "fr": "Manuscrits",
        "de": "Handschriften",
        "es": "Manuscritos",
        "it": "Manoscritti",
    },
    "unknown": {
        "zh": "其他",
        "en": "Other",
        "fr": "Autre",
        "de": "Sonstiges",
        "es": "Otros",
        "it": "Altro",
    },
}
_ALL_LABEL = {
    "zh": "全部",
    "en": "All",
    "fr": "Tout",
    "de": "Alle",
    "es": "Todo",
    "it": "Tutto",
}


def _category_label(code: str, lang: str) -> str:
    m = _CATEGORY_LABELS.get(code, {})
    return m.get(lang) or m.get("en") or code


def _resolve_name(i18n, language, legacy=None, final=None):
    """多语显示名规则:i18n[lang] → 该语言的 legacy 列(兼容未 i18n 的 stub)→ final(en 兜底,永不空)。
    避开 Joconde 脏格式(legacy 不含 artist_fr)。"""
    return (i18n or {}).get(language) or (legacy or {}).get(language) or final


def _pick(lang: str, zh, en, fr, fallback=""):
    """按语言选值，带回退链。zh→zh/en；fr→fr/en；其它→en/zh。"""
    if lang == "zh":
        return zh or en or fallback
    if lang == "fr":
        return fr or en or fallback
    return en or zh or fallback


def _pack_values(pack, source):
    """从证据包取 source 匹配的全部值(不限 tier:存量 pack 富属性为 material)。"""
    return [
        fct.get("value")
        for fct in (pack or {}).get("facts", [])
        if fct.get("source") == source and fct.get("value")
    ]


# 常见材质 → 本地化干净名(按词首关键词命中;未知原样)。ponytail: 覆盖主流画/雕塑材质,缺再加。
_MEDIUM_NORM = {
    "huile": {"zh": "油画", "en": "Oil on canvas", "fr": "Huile sur toile"},
    "oil": {"zh": "油画", "en": "Oil on canvas", "fr": "Huile sur toile"},
    "bronze": {"zh": "青铜", "en": "Bronze", "fr": "Bronze"},
    "marbre": {"zh": "大理石", "en": "Marble", "fr": "Marbre"},
    "aquarelle": {"zh": "水彩", "en": "Watercolour", "fr": "Aquarelle"},
    "pastel": {"zh": "色粉画", "en": "Pastel", "fr": "Pastel"},
    "gouache": {"zh": "水粉", "en": "Gouache", "fr": "Gouache"},
    "fusain": {"zh": "炭笔", "en": "Charcoal", "fr": "Fusain"},
    "plâtre": {"zh": "石膏", "en": "Plaster", "fr": "Plâtre"},
}


def _humanize_medium(raw, lang):
    """原始材质串(法语 Joconde / 英语 Wikidata P186)→ 本地化干净名;未命中原样。
    词首边界匹配,防 'toile' 误中 'oil'。"""
    if not raw:
        return None
    low = raw.lower()
    for kw, m in _MEDIUM_NORM.items():
        if re.search(rf"\b{kw}", low):
            return m.get(lang) or m.get("en")
    return raw


def _humanize_dimensions(raw):
    """Joconde 尺寸串(如 'en mètres : L. 0,55 ; H. 0,46' / 'H. 208, l. 264.5')→ '宽 × 高 cm'。
    ponytail: 取前两个数 + 米→厘米;格式怪异则原样返回。"""
    if not raw:
        return None
    nums = re.findall(r"\d+(?:[.,]\d+)?", raw)
    if len(nums) < 2:
        return raw
    vals = [float(n.replace(",", ".")) for n in nums[:2]]
    if "mètre" in raw.lower() or "metre" in raw.lower():  # 米 → 厘米
        vals = [v * 100 for v in vals]

    def _fmt(x):
        return f"{x:.1f}".rstrip("0").rstrip(".")

    return f"{_fmt(vals[0])} × {_fmt(vals[1])} cm"


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
            "title_zh": (o.attributes or {}).get("title_i18n", {}).get("zh")
            or o.title_zh
            or o.title_en
            or o.qid,
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
        if cs.section_code == "artist":  # artist 段是常驻卡片,不进 tabs
            continue
        row = bodies.get(cs.section_code)
        body = row.body if (row and row.status == "published") else None
        if not (body and body.strip()):
            continue  # 动态:空/未发布模块不进 tabs(料薄优雅降级)
        tabs.append(
            {
                "section_code": cs.section_code,
                "label": section_label(cs.section_code, language),
                "icon": st.icon,
                "body": body,
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
        # medium 优先证据包干净源(Wikidata P186,多值合并),回退 Joconde medium_fr
        "medium": _humanize_medium(
            ", ".join(_pack_values(obj.evidence_pack, "wikidata:P186"))
            or attrs.get("medium_fr"),
            language,
        ),
        "dimensions": _humanize_dimensions(attrs.get("dimensions")),
        "inventory": obj.inventory_number,
        "location": _pick(language, museum.name_zh, museum.name_en, museum.name_en),
        # provenance/exhibitions/bibliography 移出面板(进证据包材料级,阶段2 用),保形不删键
        "provenance": None,
        "artist_life": None,  # ponytail: 未存作者生平，接 Wikidata 作者源后再补
        "exhibitions": [],
        "bibliography": [],
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
    from app.models.artist import Artist

    aqid = attrs.get("artist_qid")
    art = db.query(Artist).filter_by(qid=aqid).first() if aqid else None
    artist_card = {
        "name": _resolve_name(
            art.name_i18n if art else None,
            language,
            {
                "zh": (art.name_zh if art else None) or obj.artist_zh,
                "en": (art.name_en if art else None) or obj.artist_en,
            },
            (art.name_en if art else None) or obj.artist_en or obj.artist_zh,
        ),
        "birth": art.birth if art else None,
        "death": art.death if art else None,
        "nationality": art.nationality if art else None,
        "notable_works": (art.notable_works if art else None) or [],
        "bio": (art.bio or {}).get(language) if art else None,
    }
    guide_body = guide_row.body if guide_row else None
    eff_status = obj.content_status
    if not (guide_body and guide_body.strip()) and not tabs:
        eff_status = "empty"
    return {
        "qid": qid,
        "category": obj.category,
        "language": language,
        "status": eff_status,
        "title": _resolve_name(
            attrs.get("title_i18n"),
            language,
            {"zh": obj.title_zh, "en": obj.title_en, "fr": attrs.get("title_fr")},
            obj.title_en or obj.title_zh or obj.qid,
        ),
        "images": images,
        "facts": facts,
        "artist": artist_card,
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

    from app.models.artist import Artist

    artist_qids = {
        (o.attributes or {}).get("artist_qid")
        for o in objs
        if (o.attributes or {}).get("artist_qid")
    }
    artists_by_qid = (
        {a.qid: a for a in db.query(Artist).filter(Artist.qid.in_(artist_qids)).all()}
        if artist_qids
        else {}
    )

    def _thumb(obj_id):
        img = images_by_obj.get(obj_id)
        if img and img.image_key:
            return storage.public_url(img.image_key)
        return img.source_url if img else None

    def _title(o):
        a = o.attributes or {}
        return _resolve_name(
            a.get("title_i18n"),
            language,
            {"zh": o.title_zh, "en": o.title_en, "fr": a.get("title_fr")},
            o.title_en or o.title_zh or o.qid,
        )

    def _artist(o):
        art = artists_by_qid.get((o.attributes or {}).get("artist_qid"))
        return (
            _resolve_name(
                art.name_i18n if art else None,
                language,
                {"zh": o.artist_zh, "en": o.artist_en},
                o.artist_en or o.artist_zh,
            )
            or ""
        )

    # content_status 按请求语言解读:对象 ready 但该语言无已发布内容 → empty(待完善),
    # 防"列表看着有、点进去空"(懒翻译入口;契约§content_status)
    lang_ready_ids = (
        {
            oid
            for (oid,) in db.query(ObjectContentSection.object_id)
            .filter(
                ObjectContentSection.object_id.in_(obj_ids),
                ObjectContentSection.language == language,
                ObjectContentSection.status == "published",
                ObjectContentSection.body.isnot(None),
            )
            .distinct()
        }
        if obj_ids
        else set()
    )

    def _status(o):
        if o.content_status == "ready" and o.id not in lang_ready_ids:
            return "empty"
        return o.content_status

    items = [
        {
            "qid": o.qid,
            "title": _title(o),
            "artist": _artist(o),
            "year": o.year,
            "thumbnail": _thumb(o.id),
            "content_status": _status(o),
        }
        for o in objs
    ]
    return {"items": items, "total": total, "limit": limit, "offset": offset}
