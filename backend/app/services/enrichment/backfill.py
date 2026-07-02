"""既有对象 content_status 回填：有已发布 section → ready，否则 stub。
部署后一次性跑（见 Phase A 收尾）。spec §8。
另:显示名回填(backfill_display_names)——契约"显示名解析时机=铺目录时"。"""

from __future__ import annotations

import re

from app.models.artist import Artist
from app.models.content import ObjectContentSection
from app.models.museum import Museum
from app.models.museum_object import MuseumObject


def backfill_content_status(db) -> dict:
    """按是否有已发布 section 设 content_status。返回 {"ready": n, "stub": m}（目标态分布）。"""
    ready_ids = {
        oid
        for (oid,) in db.query(ObjectContentSection.object_id)
        .filter_by(status="published")
        .distinct()
        .all()
    }
    counts = {"ready": 0, "stub": 0}
    for o in db.query(MuseumObject).all():
        target = "ready" if o.id in ready_ids else "stub"
        if o.content_status != target:
            o.content_status = target
        counts[target] += 1
    db.commit()
    return counts


_CREATORS_QUERY = """
SELECT ?item ?creator WHERE {{ VALUES ?item {{ {values} }} ?item wdt:P170 ?creator }}
"""


def _fetch_creators(qids, *, run_query=None) -> dict:
    """批量 作品QID → 作者QID(P170,首个)。一条 VALUES 查询搞定全馆。"""
    if not qids:
        return {}
    from app.services.enrichment.sources.wikidata_catalog import _default_run_query

    run_query = run_query or _default_run_query
    rows = run_query(_CREATORS_QUERY.format(values=" ".join(f"wd:{q}" for q in qids)))
    out = {}
    for row in rows:
        item = (row.get("item") or {}).get("value", "").rsplit("/", 1)[-1]
        creator = (row.get("creator") or {}).get("value", "").rsplit("/", 1)[-1]
        if item and creator:
            out.setdefault(item, creator)
    return out


_CJK = re.compile(r"[一-鿿]")


def _clean_i18n(i18n) -> dict:
    """剥无效值:zh 位无汉字 = 翻译失败残留(如《Vue de toits》)→ 当缺失重解析。
    ponytail: 只查 zh;加 ja/ko 等非拉丁语言时再扩。"""
    return {
        k: v
        for k, v in (i18n or {}).items()
        if v and not (k == "zh" and not _CJK.search(v))
    }


def backfill_display_names(
    db, slug, *, translator, langs, fetch_labels=None, fetch_creators=None
) -> dict:
    """铺目录后回填显示名:title_i18n + artist_qid + Artist.name_i18n(名字行,bio 留给 generate)。
    幂等:已齐语种的对象/作者跳过。契约:stub 一进目录就该有完整多语显示名。"""
    from app.services.enrichment.material import fetch_wikidata_labels
    from app.services.enrichment.pipeline import _fill_i18n

    fetch_labels = fetch_labels or fetch_wikidata_labels
    fetch_creators = fetch_creators or _fetch_creators
    m = db.query(Museum).filter_by(slug=slug).one_or_none()
    if not m:
        return {"error": "unknown museum"}
    objs = db.query(MuseumObject).filter_by(museum_id=m.id).all()
    creators = fetch_creators(
        [o.qid for o in objs if not (o.attributes or {}).get("artist_qid")]
    )
    counts = {"titles": 0, "artists": 0}
    artist_name_en: dict[str, str] = {}  # 作者QID → 来自作品行的 en 名(兜底)
    for o in objs:
        attrs = o.attributes or {}
        ti = _clean_i18n(attrs.get("title_i18n"))
        if any(not ti.get(lang) for lang in langs):
            ti = _fill_i18n(
                ti, o.title_en, fetch_labels(o.qid, langs), langs, translator
            )
            attrs = {**attrs, "title_i18n": ti}
            o.attributes = attrs
            if ti.get("zh") and not o.title_zh:
                o.title_zh = ti["zh"]
            if ti.get("en") and not o.title_en:
                o.title_en = ti["en"]  # en 轴心列回填(无 en 标签的冷门件经翻译补齐)
            counts["titles"] += 1
        aqid = attrs.get("artist_qid") or creators.get(o.qid)
        if aqid:
            if attrs.get("artist_qid") != aqid:
                o.attributes = {**attrs, "artist_qid": aqid}
            if o.artist_en:
                artist_name_en.setdefault(aqid, o.artist_en)
    for aqid, en_name in artist_name_en.items():
        art = db.query(Artist).filter_by(qid=aqid).first()
        if art is None:
            art = Artist(qid=aqid)
            db.add(art)
        if not art.name_en:
            art.name_en = en_name
        ni = _clean_i18n(art.name_i18n)
        if any(not ni.get(lang) for lang in langs):
            art.name_i18n = _fill_i18n(
                ni, art.name_en, fetch_labels(aqid, langs), langs, translator
            )
            counts["artists"] += 1
        if not art.name_zh and (art.name_i18n or {}).get("zh"):
            art.name_zh = art.name_i18n["zh"]
    db.commit()
    return counts
