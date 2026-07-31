"""既有对象 content_status 回填：有已发布 section → ready，否则 stub。
部署后一次性跑（见 Phase A 收尾）。spec §8。
另:显示名回填(backfill_display_names)——契约"显示名解析时机=铺目录时"。"""

from __future__ import annotations

import logging
import re
from concurrent.futures import ThreadPoolExecutor

from sqlalchemy.orm import sessionmaker

from app.models.artist import Artist
from app.models.content import ObjectContentSection
from app.models.museum import Museum
from app.models.museum_object import MuseumObject

logger = logging.getLogger(__name__)


def artist_names_i18n(db, o) -> dict:
    """对象作者的规范多语显示名(artists.name_i18n;无作者/无行 → {})。
    作者译名一致性:翻译 glossary 用它锁正文/问答的作者称呼(与作者卡统一)。"""
    aqid = (o.attributes or {}).get("artist_qid")
    if not aqid:
        return {}
    art = db.query(Artist).filter_by(qid=aqid).first()
    return dict(art.name_i18n or {}) if art else {}


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

    from app.services.enrichment.identity import is_wikidata_qid
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
            # P170="未知值"(作者不详)时 Wikidata 返回 blank node
            # (.well-known/genid/<32位hex>),rsplit 会把哈希当成作者 QID →
            # 建出一堆假作者行(卢浮宫实测 4642 件古物中招,撞 artists_pkey 崩)。
            # is_wikidata_qid 门控:只认真 Q 号,作者不详就留空(宁缺毋滥)。
            if item and creator and is_wikidata_qid(creator):
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
    _aname = artist_names_i18n(db, o).get(lang)
    _artists = {lang: _aname} if _aname else None
    if missing:
        title = ((o.attributes or {}).get("title_i18n") or {}).get(lang)
        _titles = {lang: title} if title else None
        # 流式先出:guide 段先翻先落(前端先显主讲解),深度模块/问答随后逐段落库。
        ordered = (["guide"] if "guide" in missing else []) + [
            c for c in missing if c != "guide"
        ]
        for code in ordered:
            res = translator.translate_object(
                {code: missing[code]}, [lang], titles=_titles, artists=_artists
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
        items = translate_qa_items(
            translator, en_qa, lang, title=_qa_title, artist=_aname
        )
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
    db, slug, *, langs, translator, limit=None, model="gpt-4o-mini", workers=8
) -> dict:
    """补语种(契约"加语言"checklist⑤):按热度逐件调 translate_object_language。幂等。

    **只取有 en 轴心内容的件**:补语种是从 en 纯翻译,没有 en 的件本就全零返回
    (交给生成)。prod 实测 louvre 17283 件里只有 303 件有内容 —— 不过滤 = 98% 空转。

    **并发**:LLM 调用是纯 I/O 等待(prod 实测 12s/段、CPU 近乎空闲),串行补两个大馆
    要 48 小时 —— 契约实战纪律⑧"CPU 占比远低于墙钟时间 = I/O 阻塞"的典型。
    每件一个任务、**线程内自带 session**(session 非线程安全,不能共享入参 db);
    与 pipeline.py 的 qa‖翻译同源纪律。单件失败跳过继续、计 errors(纪律①),
    幂等重跑补齐。
    """
    m = db.query(Museum).filter_by(slug=slug).one_or_none()
    if not m:
        return {"error": "unknown museum"}

    has_en = db.query(ObjectContentSection.object_id).filter(
        ObjectContentSection.language == "en",
        ObjectContentSection.status == "published",
        ObjectContentSection.body.isnot(None),
    )
    q = (
        db.query(MuseumObject.id)
        .filter(
            MuseumObject.museum_id == m.id,
            MuseumObject.id.in_(has_en),
        )
        .order_by(MuseumObject.popularity.desc())
    )
    if limit:
        q = q.limit(limit)
    ids = [oid for (oid,) in q.all()]

    counts = {"objects": 0, "sections": 0, "qa": 0, "bios": 0, "errors": 0}
    if not ids:
        return counts

    # 线程内 session 绑**入参 db 的同一个 engine**(而不是全局 SessionLocal):
    # 生产里两者一致,测试里则自动跟着 in-memory sqlite —— 否则这段代码不可测。
    make_session = sessionmaker(bind=db.get_bind())

    def _one(oid):
        """一件的全部语言。线程内独立 session,失败只影响这一件。"""
        s = make_session()
        try:
            o = s.get(MuseumObject, oid)
            if o is None:
                return None
            local = {"sections": 0, "qa": 0, "bios": 0}
            for lang in langs:
                c = translate_object_language(s, o, lang, translator, model)
                for k in local:
                    local[k] += c[k]
            s.commit()
            return local
        except Exception:
            s.rollback()
            logger.exception("backfill_languages: 单件失败跳过 object_id=%s", oid)
            return "error"
        finally:
            s.close()

    logger.info(
        "translate %s: %d 件待补(langs=%s, workers=%d)", slug, len(ids), langs, workers
    )
    with ThreadPoolExecutor(max_workers=max(1, workers)) as ex:
        for n, r in enumerate(ex.map(_one, ids), 1):
            if r == "error":
                counts["errors"] += 1
            elif r:
                if r["sections"] or r["qa"]:
                    counts["objects"] += 1
                for k in ("sections", "qa", "bios"):
                    counts[k] += r[k]
            if n % 50 == 0:
                logger.info(
                    "translate %s 进度 %d/%d sections=%d qa=%d errors=%d",
                    slug,
                    n,
                    len(ids),
                    counts["sections"],
                    counts["qa"],
                    counts["errors"],
                )
    return counts


_CJK = re.compile(r"[一-鿿]")


def bio_en_usable(bio) -> bool:
    """en bio 有且真的是英文→可作翻译轴心/无需重生。契约"完整性判断按语言维度":坏值=缺失。
    用语言一致性检测器统一判定(取代此前查中/法语的 _CJK/_FRENCH_SIG 打地鼠)。"""
    from app.services.enrichment.lang_detect import text_in_language

    en = (bio or {}).get("en")
    return bool(en) and text_in_language(en, "en")


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
    limit=None,
) -> dict:
    """铺目录后回填显示名:title_i18n + artist_qid + Artist.name_i18n(名字行,bio 留给 generate)。
    幂等:已齐语种的对象/作者跳过。limit=只处理前 N 件(staging 护栏小样本)。
    契约:stub 一进目录就该有完整多语显示名。"""
    from app.services.enrichment.material import (
        fetch_artist_i18n_facts,
        fetch_wikidata_labels,
    )
    from app.services.enrichment.pipeline import _fill_i18n

    # 标签批量预取(与 batch 路径同源,两条路径都不能是 N+1)。未注入时用批量缓存;
    # 注入了 fetch_labels 的调用方(测试)仍走单件语义。
    _injected = fetch_labels
    fetch_labels = fetch_labels or fetch_wikidata_labels
    _cache: dict = {}

    def _labels(qid):
        if _injected is not None:
            return _injected(qid, langs)
        if qid not in _cache:  # 未预取到的(如作者)按需补一次单件
            _cache[qid] = fetch_wikidata_labels(qid, langs)
        return _cache[qid] or {}

    fetch_creators = fetch_creators or _fetch_creators
    fetch_artist_facts_i18n = fetch_artist_facts_i18n or fetch_artist_i18n_facts
    m = db.query(Museum).filter_by(slug=slug).one_or_none()
    if not m:
        return {"error": "unknown museum"}
    objs = db.query(MuseumObject).filter_by(museum_id=m.id).all()
    if limit:
        objs = objs[:limit]
    # ⚠️ 下面两步是**长时间静默**的批量外部查询(各自可能几分钟),打点标出边界:
    # 没有它就分不清"卡在预取"还是"卡在主循环第 N 件"。
    logger.info("names %s: %d 件,开始批量取作者", slug, len(objs))
    creators = fetch_creators(
        [o.qid for o in objs if not (o.attributes or {}).get("artist_qid")]
    )
    logger.info("names %s: 作者取回 %d 条,开始批量取标签", slug, len(creators or {}))
    if _injected is None:  # 对象标签一次批量取回,后续 _labels 命中缓存
        from app.services.enrichment.material import fetch_wikidata_labels_batch

        _cache.update(fetch_wikidata_labels_batch([o.qid for o in objs], langs))
    logger.info("names %s: 标签预取完成(%d 条),进入主循环", slug, len(_cache))
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
                _rt_labels = _labels(o.qid)
                for lang in retranslate_langs:
                    if not _rt_labels.get(lang):
                        ti.pop(lang, None)
            need_fill = any(not ti.get(lang) for lang in langs)
            if need_fill or refresh_langs:
                labels = _labels(o.qid)
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
            # 与 commit 同频打点:卡死时这行就是"最后活着的位置"。
            # 没有它,3000 件的任务停在哪一件全靠猜(2026-07-30 实战教训)。
            logger.info(
                "names %s 进度 %d/%d titles=%d artists=%d errors=%d",
                slug,
                i + 1,
                len(objs),
                counts["titles"],
                counts["artists"],
                counts["errors"],
            )
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
                alabels = _labels(aqid)
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
