"""搜索引擎首发实现:进程内索引(可替换)。

打字搜索 ≠ 识别匹配:识别是整串模糊相似(difflib),搜索是子串/前缀/分词命中
(用户打"梵高"/"moulin"/"RF1668")。只复用 matcher 的归一化工具,匹配逻辑独立。

契约由端点锁定、跨引擎不变;规模越过 ~5-10 万件(卢浮+蓬皮杜级别)再换 Meilisearch,
只换本模块,前端零改动。索引进程内缓存 TTL 600s(同 matcher 模式,key=museum_id,None=全局)。
"""

from __future__ import annotations

import time

from app.models.artist import Artist
from app.models.museum import Museum
from app.models.museum_object import MuseumObject
from app.services.museum_repo import _pick
from app.services.recognition.matcher import normalize, normalize_inv

_INDEX_TTL = 600  # 秒
_index_cache: dict = {}  # museum_id -> (ts, index); None = 全局
_INV_MIN = 3  # 归一化编号 <3 位不做精确匹配(防误伤)

# 匹配分档(排序权重;换引擎后能搜到什么一致,唯排序权重可有细微差别)
_S_INV = 1.0  # 编号精确
_S_PREFIX = 0.8  # 标题前缀
_S_SUBSTR = 0.6  # 标题子串
_S_ARTIST = 0.4  # 作者子串


def build_search_index(db, museum_id=None) -> list[dict]:
    """馆(或全部)目录 → [{qid, names, artists, inv, popularity}](全语种归一化;进程内缓存)。"""
    hit = _index_cache.get(museum_id)
    if hit and time.time() - hit[0] < _INDEX_TTL:
        return hit[1]
    artists_by_qid = {}
    for a in db.query(Artist).all():
        names = {normalize(v) for v in (a.name_i18n or {}).values() if v}
        if a.name_en:
            names.add(normalize(a.name_en))
        artists_by_qid[a.qid] = names
    q = db.query(MuseumObject)
    if museum_id is not None:
        q = q.filter_by(museum_id=museum_id)
    index = []
    for o in q.all():
        attrs = o.attributes or {}
        names = {normalize(v) for v in (attrs.get("title_i18n") or {}).values() if v}
        for col in (o.title_en, o.title_zh):
            if col:
                names.add(normalize(col))
        artists = set(artists_by_qid.get(attrs.get("artist_qid"), set()))
        for col in (o.artist_en, o.artist_zh):
            if col:
                artists.add(normalize(col))
        index.append(
            {
                "id": o.id,  # 内部真实身份=UUID(qid 可能是合成把手/缺失,回查一律用 id)
                "qid": o.qid,
                "names": names - {""},
                "artists": artists - {""},
                "inv": normalize_inv(o.inventory_number) or None,
                "popularity": o.popularity or 0,
            }
        )
    _index_cache[museum_id] = (time.time(), index)
    return index


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
    无图 stub 照常在 objects 里(has_image=False)。空 query → ([], [])。"""
    # 延迟导入避免循环(service 也依赖诸多重模块)
    from app.services.recognition.service import _summary

    qn = normalize(query)
    objects = []
    if qn:
        ranked = rank(build_search_index(db, museum_id), query, limit)
        for entry, _score_val in ranked:
            # 按 UUID 回查(qid 可能是合成把手甚至 None;filter_by(qid=None) 会撞任意空 qid 件)
            o = db.query(MuseumObject).filter_by(id=entry["id"]).first()
            if not o:
                continue
            row = _summary(db, storage, o, language)
            row["year"] = o.year
            row["has_image"] = row.get("thumbnail") is not None
            objects.append(row)
    museums = []
    if museum_id is None and qn:
        museums = _search_museums(db, query, language)
    return museums, objects
