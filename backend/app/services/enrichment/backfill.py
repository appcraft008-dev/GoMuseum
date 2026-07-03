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


_CREATORS_BATCH = (
    200  # VALUES 分批:全馆千级 QID 单条查询会 URL 超长(HTTP 414,prod 教训)
)


def _fetch_creators(qids, *, run_query=None) -> dict:
    """批量 作品QID → 作者QID(P170,首个)。VALUES 分批查询。"""
    if not qids:
        return {}
    from app.services.enrichment.sources.wikidata_catalog import _default_run_query

    run_query = run_query or _default_run_query
    out: dict = {}
    qids = list(qids)
    for i in range(0, len(qids), _CREATORS_BATCH):
        batch = qids[i : i + _CREATORS_BATCH]
        rows = run_query(
            _CREATORS_QUERY.format(values=" ".join(f"wd:{q}" for q in batch))
        )
        for row in rows:
            item = (row.get("item") or {}).get("value", "").rsplit("/", 1)[-1]
            creator = (row.get("creator") or {}).get("value", "").rsplit("/", 1)[-1]
            if item and creator:
                out.setdefault(item, creator)
    return out


def translate_object_language(db, o, lang, translator, model="gpt-4o-mini") -> dict:
    """单件单语言补语种原语(懒翻译与全馆 translate 命令共用):
    缺失段/问答/该件作者 bio 从已存 en **纯翻译**落库(忠实度校验继承接地,不重生成)。幂等。
    返回 {"sections": n, "qa": n, "bios": n};对象无 en 轴心内容 → 全零(交给生成)。"""
    from app.models.content import ObjectContentSection, ObjectSuggestedQuestion
    from app.services.content_repo import (
        persist_gated_sections,
        persist_suggested_questions,
    )
    from app.services.enrichment.qa_suggester import translate_qa_items

    counts = {"sections": 0, "qa": 0, "bios": 0}
    if lang == "en":
        return counts
    en_secs = {
        r.section_code: r.body
        for r in db.query(ObjectContentSection)
        .filter_by(object_id=o.id, language="en", status="published")
        .all()
        if r.body
    }
    if not en_secs:
        return counts  # 无英语轴心内容(stub/empty)→ 交给生成,不归补语种管
    have = {
        r.section_code
        for r in db.query(ObjectContentSection)
        .filter_by(object_id=o.id, language=lang, status="published")
        .all()
        if r.body
    }
    missing = {c: b for c, b in en_secs.items() if c not in have}
    if missing:
        results = translator.translate_object(missing, [lang]).get(lang, {})
        pub, _nr = persist_gated_sections(db, o.qid, lang, results, model)
        counts["sections"] += pub
    en_qa = [
        {"question": r.question, "answer": r.answer, "status": "published"}
        for r in db.query(ObjectSuggestedQuestion)
        .filter_by(object_id=o.id, language="en", status="published")
        .order_by(ObjectSuggestedQuestion.sort)
        .all()
    ]
    if en_qa and not (
        db.query(ObjectSuggestedQuestion)
        .filter_by(object_id=o.id, language=lang, status="published")
        .first()
    ):
        items = translate_qa_items(translator, en_qa, lang)
        counts["qa"] += persist_suggested_questions(db, o.qid, lang, items, model)
    aqid = (o.attributes or {}).get("artist_qid")
    if aqid:
        art = db.query(Artist).filter_by(qid=aqid).first()
        # 坏 en(含汉字)不作轴心,防垃圾扩散;重生交给 generate 路径
        bio_en = (art.bio or {}).get("en") if art and bio_en_usable(art.bio) else None
        if bio_en and not (art.bio or {}).get(lang):
            try:
                art.bio = {
                    **(art.bio or {}),
                    lang: translator.translate_section(bio_en, lang),
                }
                counts["bios"] += 1
            except Exception:
                pass
    return counts


def backfill_languages(
    db, slug, *, langs, translator, limit=None, model="gpt-4o-mini"
) -> dict:
    """补语种(契约"加语言"checklist⑤):全馆按热度逐件调 translate_object_language。幂等。"""
    m = db.query(Museum).filter_by(slug=slug).one_or_none()
    if not m:
        return {"error": "unknown museum"}
    q = (
        db.query(MuseumObject)
        .filter_by(museum_id=m.id)
        .order_by(MuseumObject.popularity.desc())
    )
    if limit:
        q = q.limit(limit)
    counts = {"objects": 0, "sections": 0, "qa": 0, "bios": 0}
    for o in q.all():
        touched = False
        for lang in langs:
            c = translate_object_language(db, o, lang, translator, model)
            if c["sections"] or c["qa"]:
                touched = True
            for k in ("sections", "qa", "bios"):
                counts[k] += c[k]
        if touched:
            counts["objects"] += 1
    db.commit()
    return counts


_CJK = re.compile(r"[一-鿿]")


def bio_en_usable(bio) -> bool:
    """en bio 有且不是坏值(含汉字=老bug遗留的中文进 en 位)→ 可作翻译轴心/无需重生。
    契约"完整性判断按语言维度":坏值等同缺失。"""
    en = (bio or {}).get("en")
    return bool(en) and not _CJK.search(en)


def _clean_i18n(i18n) -> dict:
    """清洗显示名:剥外层书名号/引号(旧翻译残留,与权威标签风格一致);
    zh 位无汉字 = 翻译失败残留(如《Vue de toits》)→ 当缺失重解析。
    ponytail: 只查 zh;加 ja/ko 等非拉丁语言时再扩。"""
    out = {}
    for k, v in (i18n or {}).items():
        v = (v or "").strip("《》\"'“”‘’«»")
        if v and not (k == "zh" and not _CJK.search(v)):
            out[k] = v
    return out


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
        if ti != (attrs.get("title_i18n") or {}):  # 仅清洗有变化(剥号/去坏值)也落库
            attrs = {**attrs, "title_i18n": ti}
            o.attributes = attrs
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
        if ni != (art.name_i18n or {}):
            art.name_i18n = ni
        if any(not ni.get(lang) for lang in langs):
            art.name_i18n = _fill_i18n(
                ni, art.name_en, fetch_labels(aqid, langs), langs, translator
            )
            counts["artists"] += 1
        if not art.name_zh and (art.name_i18n or {}).get("zh"):
            art.name_zh = art.name_i18n["zh"]
    db.commit()
    return counts
