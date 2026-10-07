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

import logging
import re
import threading
import time
import unicodedata

from rapidfuzz import fuzz

from app.models.artist import Artist
from app.models.museum import Museum
from app.models.museum_object import MuseumObject, ObjectImage
from app.services.matching.index import core_for
from app.services.matching.normalize import normalize, normalize_inv, tokens
from app.services.museum_repo import (
    _resolve_name,
    _sized,
    museum_cities,
    museum_name,
    museum_names,
)

logger = logging.getLogger(__name__)

_INDEX_TTL = 600  # 秒
_index_cache: dict = {}  # 恒单键 None -> (ts, 全局索引)
_refresh_lock = threading.Lock()
_refreshing = False  # 后台重建中(防并发重复建)
_INV_MIN = 3  # 归一化编号 <3 位不做精确匹配(防误伤)

# 匹配分档(排序权重;换引擎后能搜到什么一致,唯排序权重可有细微差别)
_S_INV = 1.0  # 编号精确
_S_INV_DIGITS = 0.9  # 只输数字时按馆藏号数字匹配(S4):高于标题前缀,低于整串精确
_NONDIGIT = re.compile(r"\D")
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
                "inv_digits": _NONDIGIT.sub("", inv or "") or None,
                "inventory": inv,  # 原样展示,用户拿它对照说明牌
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


def _warm_core(index) -> None:
    """建匹配核心的倒排(两处共用)。倒排失败绝不拖垮搜索索引——rank 会退回原分档。"""
    try:
        from app.services.matching.index import get_core

        get_core(index)
    except Exception:
        logger.exception("matching core build failed, search falls back to tiers")


def _refresh_index_async() -> None:
    """后台重建索引(自带 session:不能跨线程用请求的 session)。失败留旧索引,
    下次过期再试——搜不到新件好过整条查询 5xx。"""
    global _refreshing
    with _refresh_lock:
        if _refreshing:
            return
        _refreshing = True

    def _run():
        global _refreshing
        try:
            from app.core.database import SessionLocal

            db2 = SessionLocal()
            try:
                index = _build_global(db2)
                _warm_core(index)  # 倒排同线程建好,请求线程不碰冷建
                _index_cache[None] = (time.time(), index)
            finally:
                db2.close()
        except Exception:
            logger.exception("search index refresh failed, keeping stale index")
        finally:
            _refreshing = False

    threading.Thread(target=_run, daemon=True, name="search-index-refresh").start()


def build_search_index(db, museum_id=None) -> list[dict]:
    """全局索引(进程内缓存);museum_id 给定时按其过滤(共享同一份缓存)。

    **过期不阻塞**:命中过期索引时先返回旧的、后台重建(stale-while-revalidate)。
    构建耗时随藏品量涨——prod 实测 24212 条目 **7.2s**,若同步重建,每个 worker
    每 TTL 就有一个倒霉用户等 7 秒(2 worker × 600s TTL)。只有进程内首次(冷启)
    才不得不同步等,故另在启动时预热。"""
    hit = _index_cache.get(None)
    if hit:
        if time.time() - hit[0] >= _INDEX_TTL:
            _refresh_index_async()  # 本次仍用旧索引,不让用户等
        index = hit[1]
    else:
        index = _build_global(db)  # 进程内首次:无旧索引可用,只能同步
        _warm_core(index)
        _index_cache[None] = (time.time(), index)
    if museum_id is None:
        return index
    return [e for e in index if e["museum_id"] == museum_id]


def warm_search_index() -> None:
    """启动预热:把冷启的那一次同步构建挪到启动时,用户请求永不撞冷建。"""
    _refresh_index_async()


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


_S_TOKEN = 0.3  # 每个词都在标题/作者里命中(含拼错/跳词/姓+标题词),但不属于上面任何一档


def _tier_scores(index: list[dict], query: str) -> dict:
    """原分档(编号/数字编号/前缀/子串/作者子串)→ {id: (entry, score)}。query 已 NFKC。

    数字退路(S4):query 为纯数字(≥3 位)且**没有任何条目拿到整串精确档**时,
    再按「馆藏号只留数字」整串相等补一档 0.9 —— 说明牌上 `INV 779`,用户只敲了 `779`。"""
    qn = normalize(query)
    qinv = normalize_inv(query)
    scored = {e["id"]: (e, s) for e in index if (s := _score(e, qn, qinv)) > 0}
    qd = query.strip()
    if (
        qd.isdigit()
        and len(qd) >= _INV_MIN
        and not any(s == _S_INV for _, s in scored.values())
    ):
        for e in index:
            if e["inv_digits"] == qd:
                prev = scored.get(e["id"], (e, 0.0))[1]
                scored[e["id"]] = (e, max(prev, _S_INV_DIGITS))
    return scored


def rank(index: list[dict], query: str, limit: int = 20) -> list[tuple[dict, float]]:
    """[(entry, score)] 降序,取 top limit。空 query → []。

    两路合并(匹配核心 10-07,spec docs/superpowers/specs/2026-10-07-matching-core-design.md):
    ①原分档(编号/前缀/子串/作者子串)原样保留——现在能搜到的一条不丢;
    ②每个查询词都在标题或作者里命中(允许拼错、末词前缀、跳词、姓+标题词),
      不属于①任何一档的给 0.3。
    排序:分档 → 同档内整名与查询越像越前 → 词元加权分 → popularity(只作最末并列键;
    它 77% 为 0,不能当权重)。
    ⚠️ 「数字退路全部列出」靠调用方 limit 够大:前端 searchProvider 传 60(search_api.dart),
    prod 已知同数字最多 23 件;0.9 档整体排在低档之前,截断只会先砍低档。"""
    # 全角→半角(中日韩输入法常切成全角数字/字母)
    query = unicodedata.normalize("NFKC", query)
    qn = normalize(query)
    if not qn:
        return []
    merged = {k: (e, s, 0.0) for k, (e, s) in _tier_scores(index, query).items()}
    try:
        core, allowed = core_for(index)
        for i, w in core.and_hits(tokens(qn), allowed).items():
            e = core.entries[i]
            prev = merged.get(e["id"])
            merged[e["id"]] = (e, prev[1] if prev else _S_TOKEN, w)
    except Exception:  # 倒排不可用时退回原分档,搜索不 5xx
        logger.exception("matching core unavailable, tier-only search")

    def sim(e):
        return max((fuzz.ratio(qn, n) for n in e["names"]), default=0)

    out = sorted(
        merged.values(),
        key=lambda x: (-x[1], -sim(x[0]), -x[2], -x[0]["popularity"]),
    )
    return [(e, s) for e, s, _ in out[:limit]]


def _search_museums(db, query: str, language: str, visible=None) -> list[dict]:
    """博物馆表 name/city 归一化子串匹配(仅全局;小集合,全表内存过滤)。
    visible=None 全可见(预览者),否则只搜这些馆 id(可见性闸)。"""
    qn = normalize(query)
    out = []
    for m in db.query(Museum).all():
        if visible is not None and m.id not in visible:
            continue
        # 十语馆名一起进匹配面:此前只有 name_zh/name_en,而匹配是归一化**子串**,
        # 于是在法语界面搜 "Musée du Louvre" 一条都搜不到("musee du louvre"
        # 不是 "louvre museum" 的子串)——用户用自己语言里的馆名反而找不到馆。
        cities = museum_cities(m)
        hay = [
            normalize(x)
            for x in (*museum_names(m).values(), *cities.values(), m.name_zh, m.name_en)
            if x
        ]
        if any(qn in h for h in hay):
            out.append(
                {
                    "slug": m.slug,
                    "name": museum_name(m, language),
                    # 十语城市名,缺该语言回退英文(与 museum_name 同一规则)。
                    "city": cities.get(language)
                    or cities.get("en")
                    or cities.get("zh"),
                }
            )
    return out


def search(
    db,
    storage,
    query: str,
    *,
    museum_id=None,
    language: str = "zh",
    limit: int = 20,
    visible=None,
) -> tuple[list[dict], list[dict]]:
    """契约实现:(museums, objects)。museum_id 给定=馆域(无 museums 段);None=全局。
    无图 stub 照常在 objects 里(has_image=False)。空 query → ([], [])。
    objects 段全部来自索引条目,不回表(与原 _summary 输出形状一致)。"""
    qn = normalize(query)
    objects = []
    if qn:
        index = build_search_index(db, museum_id)
        if visible is not None:
            # 索引不带可见性,查询时过滤(索引是进程内缓存,放出的 SQL 碰不到它)
            index = [e for e in index if e["museum_id"] in visible]
        for entry, _score_val in rank(index, query, limit):
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
                    "inventory": entry["inventory"],
                }
            )
    museums = []
    if museum_id is None and qn:
        museums = _search_museums(db, query, language, visible)
    return museums, objects
