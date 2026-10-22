"""网站只读数据层:城市 → 馆 → 作品 / 作者。

规矩(spec 2026-10-22-website-v1 §三):
- 一律按**外人**可见性(`published_at IS NOT NULL`),隐身馆连城市都不露。
- 「有内容」= 该**请求语言**有已发布、非空的 guide,且有可展示图(同 App 列表口径)。
- 只读,不调内容接口、不碰懒生成。
"""

import unicodedata
from dataclasses import dataclass, field

from sqlalchemy import and_, exists, func

from app.models.artist import Artist
from app.models.content import ObjectContentSection
from app.models.museum import Museum
from app.models.museum_object import MuseumObject, ObjectImage
from app.services.enrichment.catalog import RANK_LAST
from app.services.museum_repo import (
    _category_label,
    _museum_ranks,
    _resolve_name,
    _sized,
    museum_cities,
)
from app.services.must_see import has_image_clause, must_see_order
from app.services.recognition.tiles import HIDDEN_ROLES
from app.services.storage import get_object_storage

LANGS: tuple[str, ...] = (
    "en",
    "fr",
    "zh",
    "zh-hant",
    "de",
    "es",
    "it",
    "pl",
    "ja",
    "ko",
)
# 薄页门槛:该语言有内容的件少于它 → noindex、不进 sitemap/hreflang(页面照样能开)
THIN_MUSEUM = 20
THIN_ARTIST = 3


@dataclass
class City:
    slug: str
    names: dict[str, str]
    country: str
    museums: list[Museum] = field(default_factory=list)


@dataclass
class WorkCard:
    qid: str
    museum_slug: str
    city: str
    title: str
    artist: str | None
    year: str | None
    thumb_url: str | None


@dataclass
class ArtistCount:
    qid: str
    name: str
    count: int


def city_slug(city_en: str) -> str:
    s = unicodedata.normalize("NFKD", city_en or "")
    s = "".join(c for c in s if not unicodedata.combining(c)).lower()
    out = "".join(c if c.isalnum() else "-" for c in s)
    return "-".join(p for p in out.split("-") if p)


def museum_city_slug(museum: Museum) -> str:
    return city_slug(museum_cities(museum).get("en") or museum.city_en or "")


def _rank(slug: str) -> int:
    return _museum_ranks().get(slug, RANK_LAST)


def public_museums(db) -> list[Museum]:
    rows = db.query(Museum).filter(Museum.published_at.isnot(None)).all()
    return sorted(rows, key=lambda m: (_rank(m.slug), m.slug))


def public_cities(db) -> list[City]:
    cities: dict[str, City] = {}
    for m in public_museums(db):
        slug = museum_city_slug(m)
        if not slug:
            continue
        c = cities.setdefault(
            slug, City(slug=slug, names=museum_cities(m), country=m.country or "")
        )
        c.museums.append(m)
    return list(cities.values())  # 馆已按 rank 排,城市顺序 = 其首馆 rank


def find_city(db, city: str) -> City | None:
    return next((c for c in public_cities(db) if c.slug == city), None)


def find_museum(db, city: str, museum_slug: str) -> Museum | None:
    m = (
        db.query(Museum)
        .filter(Museum.slug == museum_slug, Museum.published_at.isnot(None))
        .one_or_none()
    )
    return m if m is not None and museum_city_slug(m) == city else None


def _has_guide(language: str):
    return exists().where(
        and_(
            ObjectContentSection.object_id == MuseumObject.id,
            ObjectContentSection.section_code == "guide",
            ObjectContentSection.status == "published",
            ObjectContentSection.language == language,
            ObjectContentSection.body.isnot(None),
            func.trim(ObjectContentSection.body) != "",
        )
    )


def _artist_col():
    return MuseumObject.attributes["artist_qid"].as_string()


def _base(db, museum_ids, language):
    return db.query(MuseumObject).filter(
        MuseumObject.museum_id.in_(museum_ids),
        _has_guide(language),
        has_image_clause(),
    )


def _artist_names(db, qids, language) -> dict[str, str]:
    if not qids:
        return {}
    out = {}
    for a in db.query(Artist).filter(Artist.qid.in_(list(qids))):
        name = _resolve_name(
            a.name_i18n,
            language,
            {"zh": a.name_zh, "en": a.name_en},
            a.name_en or a.name_zh,
        )
        if name:  # 没名字的作者卡(佚名/哈希 qid)不显示,绝不把 qid 当名字
            out[a.qid] = name
    return out


def work_title(o: MuseumObject, language: str) -> str:
    attrs = o.attributes or {}
    return _resolve_name(
        attrs.get("title_i18n"),
        language,
        {"zh": o.title_zh, "en": o.title_en, "fr": attrs.get("title_fr")},
        o.title_en or o.title_zh or o.qid,
    )


def to_cards(db, objs: list[MuseumObject], language: str) -> list[WorkCard]:
    if not objs:
        return []
    museums = {
        m.id: m
        for m in db.query(Museum).filter(Museum.id.in_({o.museum_id for o in objs}))
    }
    thumbs: dict = {}
    for img in (
        db.query(ObjectImage)
        .filter(
            ObjectImage.object_id.in_([o.id for o in objs]),
            ObjectImage.role.notin_(HIDDEN_ROLES),
            ObjectImage.image_key.isnot(None),
        )
        .order_by(ObjectImage.sort)
    ):
        thumbs.setdefault(img.object_id, img.image_key)
    names = _artist_names(
        db, {(o.attributes or {}).get("artist_qid") for o in objs} - {None}, language
    )
    storage = get_object_storage()
    cards = []
    for o in objs:
        m = museums[o.museum_id]
        aq = (o.attributes or {}).get("artist_qid")
        key = thumbs.get(o.id)
        cards.append(
            WorkCard(
                qid=o.qid,
                museum_slug=m.slug,
                city=museum_city_slug(m),
                title=work_title(o, language),
                artist=names.get(aq) or o.artist_en or o.artist_zh,
                year=o.year,
                thumb_url=_sized(storage, key, "thumb") if key else None,
            )
        )
    return cards


def list_works(
    db,
    museum_ids: list,
    language: str,
    *,
    artist_qid: str | None = None,
    category: str | None = None,
    page: int = 1,
    page_size: int = 48,
) -> tuple[list[WorkCard], int]:
    q = _base(db, museum_ids, language)
    if artist_qid:
        q = q.filter(_artist_col() == artist_qid)
    if category:
        q = q.filter(MuseumObject.category == category)
    total = q.count()
    head = []
    if len(museum_ids) == 1:
        slug = db.query(Museum.slug).filter(Museum.id == museum_ids[0]).scalar()
        head = must_see_order(slug)
    objs = (
        q.order_by(*head, MuseumObject.popularity.desc(), MuseumObject.id)
        .offset((max(page, 1) - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return to_cards(db, objs, language), total


def top_artists(db, museum_ids: list, language: str, limit: int = 24) -> list:
    col = _artist_col()
    rows = (
        _base(db, museum_ids, language)
        .with_entities(col, func.count(MuseumObject.id))
        .filter(col.isnot(None))
        .group_by(col)
        .order_by(func.count(MuseumObject.id).desc(), col)
        .limit(limit)
        .all()
    )
    names = _artist_names(db, {q for q, _ in rows}, language)
    return [ArtistCount(q, names[q], n) for q, n in rows if q in names]


def categories(db, museum_ids: list, language: str) -> list[tuple[str, str, int]]:
    rows = (
        _base(db, museum_ids, language)
        .with_entities(MuseumObject.category, func.count(MuseumObject.id))
        .group_by(MuseumObject.category)
        .order_by(func.count(MuseumObject.id).desc())
        .all()
    )
    return [(c, _category_label(c, language), n) for c, n in rows]


def guide_count(db, museum_ids: list, language: str) -> int:
    return _base(db, museum_ids, language).count()


def page_languages(db, museum_ids: list, *, artist_qid: str | None = None) -> list:
    """达到薄页门槛的语言(按 LANGS 顺序)。"""
    floor = THIN_ARTIST if artist_qid else THIN_MUSEUM
    out = []
    for lang in LANGS:
        q = _base(db, museum_ids, lang)
        if artist_qid:
            q = q.filter(_artist_col() == artist_qid)
        if q.count() >= floor:
            out.append(lang)
    return out


def cards_for_qids(db, museum_ids: list, language: str, qids: list[str]) -> list:
    """搜索结果 → 卡片:只留该语言有内容的件,保持传入顺序。"""
    if not qids:
        return []
    objs = {
        o.qid: o
        for o in _base(db, museum_ids, language).filter(MuseumObject.qid.in_(qids))
    }
    return to_cards(db, [objs[q] for q in qids if q in objs], language)


def _guide_rows(db, museum_ids):
    """(qid, artist_qid, language) —— 每件每门有已发布 guide 且有图的语言一行。"""
    return (
        db.query(MuseumObject.qid, _artist_col(), ObjectContentSection.language)
        .join(ObjectContentSection, ObjectContentSection.object_id == MuseumObject.id)
        .filter(
            MuseumObject.museum_id.in_(museum_ids),
            ObjectContentSection.section_code == "guide",
            ObjectContentSection.status == "published",
            ObjectContentSection.body.isnot(None),
            func.trim(ObjectContentSection.body) != "",
            ObjectContentSection.language.in_(LANGS),
            has_image_clause(),
        )
        .all()
    )


def work_languages(db, museum_ids: list) -> dict[str, list[str]]:
    """qid → 有内容的语言(按 LANGS 顺序)。sitemap 一次查完,不逐件查。"""
    out: dict[str, set] = {}
    for qid, _a, lang in _guide_rows(db, museum_ids):
        out.setdefault(qid, set()).add(lang)
    return {q: [lg for lg in LANGS if lg in s] for q, s in out.items()}


def artist_languages(db, museum_ids: list) -> dict[str, list[str]]:
    """artist_qid → 达到作者页门槛的语言(按 LANGS 顺序)。"""
    counts: dict[str, dict[str, int]] = {}
    for _q, aq, lang in _guide_rows(db, museum_ids):
        if aq:
            c = counts.setdefault(aq, {})
            c[lang] = c.get(lang, 0) + 1
    known = set(_artist_names(db, set(counts), "en"))  # 有名字的才有作者页
    return {
        aq: [lg for lg in LANGS if c.get(lg, 0) >= THIN_ARTIST]
        for aq, c in counts.items()
        if aq in known
    }
