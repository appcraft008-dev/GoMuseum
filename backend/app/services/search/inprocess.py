"""搜索引擎首发实现:进程内索引(可替换)。

打字搜索 ≠ 识别匹配:识别是整串模糊相似(difflib),搜索是子串/前缀/分词命中
(用户打"梵高"/"moulin"/"RF1668")。只复用 matcher 的归一化工具,匹配逻辑独立。

契约由端点锁定、跨引擎不变;规模越过 ~5-10 万件(卢浮+蓬皮杜级别)再换 Meilisearch,
只换本模块,前端零改动。

性能形状(修"转圈圈",2026-07-16):
- 单一全局索引(缓存键恒为 None,TTL 600s),馆域=按 museum_id 过滤,不再每馆独立冷建;
- 冷建只查需要的列,不拖 sources/evidence_pack 大 JSONB(原冷建数秒的主因);
- 展示字段(标题/作者 i18n、年代、馆 slug、图 key)建索引时装进条目,
  search() 纯内存出结果,消灭原先每条结果 4 次回表的 N+1。
"""

from __future__ import annotations

import time

from app.models.artist import Artist
from app.models.museum import Museum
from app.models.museum_object import MuseumObject, ObjectImage
from app.services.museum_repo import _pick, _resolve_name, _sized
from app.services.recognition.matcher import normalize, normalize_inv

_INDEX_TTL = 600  # 秒
_index_cache: dict = {}  # 恒单键 None -> (ts, 全局索引)
_INV_MIN = 3  # 归一化编号 <3 位不做精确匹配(防误伤)

# 匹配分档(排序权重;换引擎后能搜到什么一致,唯排序权重可有细微差别)
_S_INV = 1.0  # 编号精确
_S_PREFIX = 0.8  # 标题前缀
_S_SUBSTR = 0.6  # 标题子串
_S_ARTIST = 0.4  # 作者子串


def _build_global(db) -> list[dict]:
    """全表(仅所需列)→ 索引条目(归一化匹配集 + 展示字段自带)。固定 4 条 SQL,与件数无关。"""
    artists_by_qid = {}  # qid -> (归一化名集, name_i18n)
    for qid, name_en, name_i18n in db.query(
        Artist.qid, Artist.name_en, Artist.name_i18n
    ):
        names = {normalize(v) for v in (name_i18n or {}).values() if v}
        if name_en:
            names.add(normalize(name_en))
        artists_by_qid[qid] = (names, name_i18n)
    slug_by_museum = dict(db.query(Museum.id, Museum.slug))
    img_by_object = {}  # object_id -> (image_key, source_url) 取 primary 最小 sort
    for oid, key, url in (
        db.query(ObjectImage.object_id, ObjectImage.image_key, ObjectImage.source_url)
        .filter_by(role="primary")
        .order_by(ObjectImage.sort)
    ):
        img_by_object.setdefault(oid, (key, url))
    index = []
    rows = db.query(
        MuseumObject.id,
        MuseumObject.qid,
        MuseumObject.museum_id,
        MuseumObject.title_zh,
        MuseumObject.title_en,
        MuseumObject.artist_zh,
        MuseumObject.artist_en,
        MuseumObject.year,
        MuseumObject.popularity,
        MuseumObject.inventory_number,
        MuseumObject.attributes,
    )
    for oid, qid, mid, t_zh, t_en, a_zh, a_en, year, pop, inv, attrs in rows:
        attrs = attrs or {}
        title_i18n = attrs.get("title_i18n") or {}
        names = {normalize(v) for v in title_i18n.values() if v}
        for col in (t_en, t_zh):
            if col:
                names.add(normalize(col))
        a_names, a_i18n = artists_by_qid.get(attrs.get("artist_qid"), (set(), None))
        artist_names = set(a_names)
        for col in (a_en, a_zh):
            if col:
                artist_names.add(normalize(col))
        image_key, image_url = img_by_object.get(oid, (None, None))
        index.append(
            {
                "id": oid,  # 内部真实身份=UUID(qid 可能是合成把手/缺失)
                "qid": qid,
                "museum_id": mid,
                "museum_slug": slug_by_museum.get(mid),
                "names": names - {""},
                "artists": artist_names - {""},
                "inv": normalize_inv(inv) or None,
                "popularity": pop or 0,
                # 展示字段自带 → search() 零回表
                "title_i18n": title_i18n,
                "title_zh": t_zh,
                "title_en": t_en,
                "artist_i18n": a_i18n,
                "artist_zh": a_zh,
                "artist_en": a_en,
                "year": year,
                "image_key": image_key,
                "image_url": image_url,
            }
        )
    return index


def build_search_index(db, museum_id=None) -> list[dict]:
    """全局索引(进程内缓存);museum_id 给定时按其过滤(共享同一份缓存)。"""
    hit = _index_cache.get(None)
    if hit and time.time() - hit[0] < _INDEX_TTL:
        index = hit[1]
    else:
        index = _build_global(db)
        _index_cache[None] = (time.time(), index)
    if museum_id is None:
        return index
    return [e for e in index if e["museum_id"] == museum_id]


def _score(entry: dict, qn: str, qinv: str) -> float:
    """三路(编号/标题/作者)取最高档;qn 已归一化且非空。"""
    if entry["inv"] and len(qinv) >= _INV_MIN and entry["inv"] == qinv:
        return _S_INV
    if any(n.startswith(qn) for n in entry["names"]):
        return _S_PREFIX
    if any(qn in n for n in entry["names"]):
        return _S_SUBSTR
    if any(qn in a for a in entry["artists"]):
        return _S_ARTIST
    return 0.0


def rank(index: list[dict], query: str, limit: int = 20) -> list[tuple[dict, float]]:
    """[(entry, score)] 降序,同分按 popularity 降序,取 top limit。空 query → []。"""
    qn = normalize(query)
    if not qn:
        return []
    qinv = normalize_inv(query)
    scored = [(e, s) for e in index if (s := _score(e, qn, qinv)) > 0]
    scored.sort(key=lambda es: (-es[1], -es[0]["popularity"]))
    return scored[:limit]


def _search_museums(db, query: str, language: str) -> list[dict]:
    """博物馆表 name/city 归一化子串匹配(仅全局;小集合,全表内存过滤)。"""
    qn = normalize(query)
    out = []
    for m in db.query(Museum).all():
        hay = [normalize(x) for x in (m.name_zh, m.name_en, m.city_zh, m.city_en) if x]
        if any(qn in h for h in hay):
            out.append(
                {
                    "slug": m.slug,
                    "name": _pick(language, m.name_zh, m.name_en, None),
                    "city": _pick(language, m.city_zh, m.city_en, None),
                }
            )
    return out


def search(
    db, storage, query: str, *, museum_id=None, language: str = "zh", limit: int = 20
) -> tuple[list[dict], list[dict]]:
    """契约实现:(museums, objects)。museum_id 给定=馆域(无 museums 段);None=全局。
    无图 stub 照常在 objects 里(has_image=False)。空 query → ([], [])。
    objects 段全部来自索引条目,不回表(与原 _summary 输出形状一致)。"""
    qn = normalize(query)
    objects = []
    if qn:
        for entry, _score_val in rank(build_search_index(db, museum_id), query, limit):
            thumbnail = None
            if entry["image_key"]:
                thumbnail = _sized(storage, entry["image_key"], "thumb")
            elif entry["image_url"]:
                thumbnail = entry["image_url"]
            objects.append(
                {
                    "qid": entry["qid"],
                    "museum": entry["museum_slug"],
                    "title": _resolve_name(
                        entry["title_i18n"],
                        language,
                        {"zh": entry["title_zh"], "en": entry["title_en"]},
                        entry["title_en"] or entry["title_zh"] or entry["qid"],
                    ),
                    "artist": _resolve_name(
                        entry["artist_i18n"],
                        language,
                        {"zh": entry["artist_zh"], "en": entry["artist_en"]},
                        entry["artist_en"] or entry["artist_zh"],
                    ),
                    "thumbnail": thumbnail,
                    "year": entry["year"],
                    "has_image": thumbnail is not None,
                }
            )
    museums = []
    if museum_id is None and qn:
        museums = _search_museums(db, query, language)
    return museums, objects
