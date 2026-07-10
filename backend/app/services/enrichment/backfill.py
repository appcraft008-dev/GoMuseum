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


def _fetch_creators(qids, *, run_query=None, retry_wait=5) -> dict:
    """批量 作品QID → 作者QID(P170,首个)。VALUES 分批查询。
    单批失败重试一次,仍失败跳过该批(Wikidata 502 教训:不炸全局,幂等重跑再补)。"""
    if not qids:
        return {}
    import logging
    import time

    from app.services.enrichment.sources.wikidata_catalog import _default_run_query

    run_query = run_query or _default_run_query
    out: dict = {}
    qids = list(qids)
    for i in range(0, len(qids), _CREATORS_BATCH):
        batch = qids[i : i + _CREATORS_BATCH]
        sparql = _CREATORS_QUERY.format(values=" ".join(f"wd:{q}" for q in batch))
        rows = None
        for attempt in (1, 2):
            try:
                rows = run_query(sparql)
                break
            except Exception:
                if attempt == 1:
                    time.sleep(retry_wait)
                else:
                    logging.getLogger(__name__).exception(
                        "creators batch failed, skip %d qids", len(batch)
                    )
        if rows is None:
            continue
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
        title = ((o.attributes or {}).get("title_i18n") or {}).get(lang)
        _titles = {lang: title} if title else None
        # 流式先出:guide 段先翻先落(前端先显主讲解),深度模块/问答随后逐段落库。
        ordered = (["guide"] if "guide" in missing else []) + [
            c for c in missing if c != "guide"
        ]
        for code in ordered:
            res = translator.translate_object(
                {code: missing[code]}, [lang], titles=_titles
            ).get(lang, {})
            pub, _nr = persist_gated_sections(db, o.qid, lang, res, model)
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
        _qa_title = ((o.attributes or {}).get("title_i18n") or {}).get(lang)
        items = translate_qa_items(translator, en_qa, lang, title=_qa_title)
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


# en 位混入法语的特征词(法国作者的 bio 常镜像法语源材料)。坏值=不可作轴心,需重生。
_FRENCH_SIG = re.compile(
    r"\b(né|née|était|est un|est une|dans une|peintre français|française|"
    r"sculpteur français)\b",
    re.IGNORECASE,
)


def bio_en_usable(bio) -> bool:
    """en bio 有且不是坏值→可作翻译轴心/无需重生。契约"完整性判断按语言维度":坏值等同缺失。
    坏值 = 含汉字(中文混入)或含法语特征词(法语镜像,问题3)。"""
    en = (bio or {}).get("en")
    return bool(en) and not _CJK.search(en) and not _FRENCH_SIG.search(en)


def _clean_i18n(i18n) -> dict:
    """清洗显示名:剥外层书名号/引号(旧翻译残留,与权威标签风格一致);
    zh 位无汉字 = 翻译失败残留(如《Vue de toits》)→ 当缺失重解析。
    ponytail: 只查 zh;加 ja/ko 等非拉丁语言时再扩。"""
    out = {}
    for k, v in (i18n or {}).items():
        v = (v or "").strip("《》\"'“”‘’«»")
        if v and not (k in ("zh", "zh-hant") and not _CJK.search(v)):
            out[k] = v
    return out


def fill_artist_i18n_facts(art, langs, translator, data) -> bool:
    """作者国籍/代表作多语填充(交接③):权威标签优先→已有保留→en 轴(legacy 列)翻译兜底。
    data=fetch_artist_i18n_facts 结果。幂等只补缺;返回是否有变更。"""
    nat = {**(data.get("nationality_i18n") or {}), **(art.nationality_i18n or {})}
    works = {**(data.get("notable_works_i18n") or {}), **(art.notable_works_i18n or {})}
    if not nat.get("en") and art.nationality:
        nat["en"] = art.nationality
    if not works.get("en") and art.notable_works:
        works["en"] = list(art.notable_works)
    tr = getattr(translator, "translate_name", None) or getattr(
        translator, "translate_section", None
    )
    for lang in langs:
        if not nat.get(lang) and nat.get("en") and tr:
            try:
                nat[lang] = tr(nat["en"], lang)
            except Exception:
                pass
        if not works.get(lang) and works.get("en") and tr:
            try:
                works[lang] = [tr(w, lang) for w in works["en"]]
            except Exception:
                pass
    changed = nat != (art.nationality_i18n or {}) or works != (
        art.notable_works_i18n or {}
    )
    if nat:
        art.nationality_i18n = nat
    if works:
        art.notable_works_i18n = works
    return changed


def backfill_display_names(
    db,
    slug,
    *,
    translator,
    langs,
    fetch_labels=None,
    fetch_creators=None,
    fetch_artist_facts_i18n=None,
    refresh_langs=None,
    retranslate_langs=None,
) -> dict:
    """铺目录后回填显示名:title_i18n + artist_qid + Artist.name_i18n(名字行,bio 留给 generate)。
    幂等:已齐语种的对象/作者跳过。契约:stub 一进目录就该有完整多语显示名。"""
    from app.services.enrichment.material import (
        fetch_artist_i18n_facts,
        fetch_wikidata_labels,
    )
    from app.services.enrichment.pipeline import _fill_i18n

    fetch_labels = fetch_labels or fetch_wikidata_labels
    fetch_creators = fetch_creators or _fetch_creators
    fetch_artist_facts_i18n = fetch_artist_facts_i18n or fetch_artist_i18n_facts
    m = db.query(Museum).filter_by(slug=slug).one_or_none()
    if not m:
        return {"error": "unknown museum"}
    objs = db.query(MuseumObject).filter_by(museum_id=m.id).all()
    creators = fetch_creators(
        [o.qid for o in objs if not (o.attributes or {}).get("artist_qid")]
    )
    counts = {"titles": 0, "artists": 0, "errors": 0}
    artist_name_en: dict[str, str] = {}  # 作者QID → 来自作品行的 en 名(兜底)
    for i, o in enumerate(objs):
        # 单件容错:一次 Wikidata 超时不炸整馆(prod 253/1942 即死教训);失败跳过重跑再补
        try:
            attrs = o.attributes or {}
            ti = _clean_i18n(attrs.get("title_i18n"))
            if ti != (attrs.get("title_i18n") or {}):  # 仅清洗有变化(剥号/去坏值)也落库
                attrs = {**attrs, "title_i18n": ti}
                o.attributes = attrs
            # retranslate:该语言无权威标签则丢弃机翻值,下面 _fill_i18n 用改进版重译
            if retranslate_langs:
                _rt_labels = fetch_labels(o.qid, langs)
                for lang in retranslate_langs:
                    if not _rt_labels.get(lang):
                        ti.pop(lang, None)
            need_fill = any(not ti.get(lang) for lang in langs)
            if need_fill or refresh_langs:
                labels = fetch_labels(o.qid, langs)
                # refresh:该语言有权威标签则覆盖存量(繁→简修复);无标签保留(翻译值不动)
                for lang in refresh_langs or []:
                    if labels.get(lang) and labels[lang] != ti.get(lang):
                        ti = {**ti, lang: labels[lang]}
                        attrs = {**attrs, "title_i18n": ti}
                        o.attributes = attrs
            if need_fill:
                ti = _fill_i18n(ti, o.title_en, labels, langs, translator)
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
        except Exception:
            import logging

            logging.getLogger(__name__).exception("names backfill failed: %s", o.qid)
            counts["errors"] += 1
        if (i + 1) % 50 == 0:
            db.commit()  # 分批落盘:中途崩溃不丢已完成进度
    for j, (aqid, en_name) in enumerate(artist_name_en.items()):
        try:
            art = db.query(Artist).filter_by(qid=aqid).first()
            if art is None:
                art = Artist(qid=aqid)
                db.add(art)
            if not art.name_en:
                art.name_en = en_name
            ni = _clean_i18n(art.name_i18n)
            if ni != (art.name_i18n or {}):
                art.name_i18n = ni
            need_fill_a = any(not ni.get(lang) for lang in langs)
            if need_fill_a or refresh_langs:
                alabels = fetch_labels(aqid, langs)
                for lang in refresh_langs or []:
                    if alabels.get(lang) and alabels[lang] != ni.get(lang):
                        ni = {**ni, lang: alabels[lang]}
                        art.name_i18n = ni
                        if lang == "zh":
                            art.name_zh = alabels[lang]
            if need_fill_a:
                art.name_i18n = _fill_i18n(ni, art.name_en, alabels, langs, translator)
                counts["artists"] += 1
            if not art.name_zh and (art.name_i18n or {}).get("zh"):
                art.name_zh = art.name_i18n["zh"]
            # 国籍/代表作多语(交接③):缺语种才触网,幂等
            need = [
                lang
                for lang in langs
                if not (art.nationality_i18n or {}).get(lang)
                or not (art.notable_works_i18n or {}).get(lang)
            ]
            if need:
                fill_artist_i18n_facts(
                    art, langs, translator, fetch_artist_facts_i18n(aqid, langs)
                )
        except Exception:
            import logging

            logging.getLogger(__name__).exception("artist names failed: %s", aqid)
            counts["errors"] += 1
        if (j + 1) % 50 == 0:
            db.commit()
    db.commit()
    return counts
