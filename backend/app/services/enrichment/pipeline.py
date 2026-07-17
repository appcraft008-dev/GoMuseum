"""generate 编排：DB 对象 → 生成(2a) → 质量闸(2b) → 落英语 → 翻译(2c) → 按语言落库。
组件注入（enricher/gate/translator），整体离线可测。spec §7 / §17 三触发之一。"""

from __future__ import annotations

import logging

from app.models.content import ObjectContentSection
from app.models.museum import Museum
from app.models.museum_object import MuseumObject
from app.services.content_repo import (
    persist_gated_sections,
    persist_suggested_questions,
)
from app.services.enrichment.category_config import guide_target_chars, sections_for
from app.services.enrichment.content_enricher import build_material
from app.services.enrichment.material import fetch_object_material

logger = logging.getLogger(__name__)

# 标"Creation year"消歧：避免 fact-consistency 判官把首展/收购/修复年误判为与创作年冲突。
_FACT_KEYS = [("Title", "title_en"), ("Artist", "artist_en"), ("Creation year", "year")]


def _artist_facts(qid):
    """薄包装：调结构化作者属性获取（测试 monkeypatch 此处避免触网）。"""
    from app.services.enrichment.material import fetch_artist_facts

    return fetch_artist_facts(qid)


def _wikidata_labels(qid, langs):
    from app.services.enrichment.material import fetch_wikidata_labels

    return fetch_wikidata_labels(qid, langs)


def _artist_i18n_facts(qid, langs):
    """薄包装:作者国籍/代表作多语标签(测试 monkeypatch 此处避免触网)。"""
    from app.services.enrichment.material import fetch_artist_i18n_facts

    return fetch_artist_i18n_facts(qid, langs)


def _fill_i18n(existing, en_name, labels, langs, translator):
    """权威标签优先(含 en:纠正目录误存非英文标签);缺的从轴心翻译。
    轴心 = en(名或标签),en 也没有则任一权威标签(冷门件常无 en 标签,如只有 fr)。返回 {lang: name}。"""
    out = dict(existing or {})
    for lang in langs:
        if not out.get(lang) and labels.get(lang):
            out[lang] = labels[lang]
    if en_name and not out.get("en"):
        out["en"] = en_name
    pivot = out.get("en") or next((out[x] for x in langs if out.get(x)), None)
    # 显示名优先走 translate_name(标题专用 prompt);老 translator 兼容 translate_section
    tr = getattr(translator, "translate_name", None) or getattr(
        translator, "translate_section", None
    )
    if not pivot or tr is None:
        return out
    for lang in langs:
        if out.get(lang):
            continue
        try:
            out[lang] = tr(pivot, lang)
        except Exception:
            pass
    return out


def _row_to_obj(o) -> dict:
    """MuseumObject 行 → build_material/生成器吃的 obj dict。"""
    return {
        "title_en": o.title_en,
        "artist_en": o.artist_en,
        "year": o.year,
        "category": o.category,
        "attributes": o.attributes or {},
        "evidence_pack": getattr(o, "evidence_pack", None),
        "popularity": getattr(o, "popularity", None),
    }


def _facts_text(obj: dict) -> str:
    """结构化硬事实文本（供质量闸事实对账）；缺字段跳过。"""
    lines = []
    for label, key in _FACT_KEYS:
        v = obj.get(key)
        if v:
            lines.append(f"- {label}: {v}")
    return "\n".join(lines)


def _has_published_en(db, object_id) -> bool:
    return (
        db.query(ObjectContentSection)
        .filter_by(object_id=object_id, language="en", status="published")
        .first()
        is not None
    )


def generate_object(
    db,
    qid,
    *,
    enricher,
    gate,
    translator,
    target_langs,
    model,
    force=False,
    qa_suggester=None,
    registry=None,
    country_lang=None,
    lang_priority=None,
) -> dict:
    """单件：生成→质量闸→落英语→逐语言翻译落库。幂等跳过已发布英语（除非 force）。
    lang_priority=请求者语言(懒生成场景):排队首,翻完即落库,用户最快看到自己的语言。"""
    if lang_priority and lang_priority in target_langs:
        target_langs = [lang_priority] + [
            lang for lang in target_langs if lang != lang_priority
        ]
    o = db.query(MuseumObject).filter_by(qid=qid).one_or_none()
    if not o:
        return {"qid": qid, "skipped": "absent"}
    if not force and _has_published_en(db, o.id):
        return {"qid": qid, "skipped": "exists"}

    if registry is not None and o.content_status == "stub":
        attrs = o.attributes or {}
        fetched = fetch_object_material(
            o.qid,
            attrs.get("external_ids") or {},
            attrs.get("wiki_titles") or {},
            registry,
        )
        if fetched:
            o.attributes = {**attrs, **fetched}
            db.flush()

    if registry is not None:
        try:
            wlabels = _wikidata_labels(o.qid, target_langs)
            ti = _fill_i18n(
                (o.attributes or {}).get("title_i18n"),
                o.title_en,
                wlabels,
                target_langs,
                translator,
            )
            o.attributes = {**(o.attributes or {}), "title_i18n": ti}
            if ti.get("zh") and not o.title_zh:
                o.title_zh = ti["zh"]
            db.flush()
        except Exception:
            pass

        from app.services.enrichment.material import fetch_artist_material

        # Wikidata/网络抖动不应拖垮整件生成 → 失败则当无作者材料继续
        try:
            artist_mat = fetch_artist_material(
                o.qid, registry, country_lang=country_lang or "fr"
            )
        except Exception:
            artist_mat = {}
        if artist_mat:
            o.attributes = {**(o.attributes or {}), **artist_mat}
            db.flush()

        try:
            af = _artist_facts(o.qid)
        except Exception:
            af = {}
        if af:
            o.attributes = {**(o.attributes or {}), **af}
            db.flush()

        aqid = (af or {}).get("artist_qid")
        if aqid:
            o.attributes = {**(o.attributes or {}), "artist_qid": aqid}
            db.flush()

    def _enrich_artist_and_titles():
        """作者实体(bio/名字/国籍多语)+ 中文标题回退。guide 正文不消费这些
        (build_material 不读 Artist.bio)→ 延后到"请求语言 guide 落库"之后跑,
        把它们从首屏关键路径挪走,缩短用户 TTFC。质量/成本/调用集不变,仅换顺序。"""
        aqid = (af or {}).get("artist_qid") if registry is not None else None
        if aqid:
            from app.models.artist import Artist
            from app.services.enrichment.backfill import bio_en_usable

            art = db.query(Artist).filter_by(qid=aqid).first()
            # force 刷新已存作者;bio 空或 en 位坏值(老bug遗留中文)也重生成
            # (契约"完整性判断按语言维度":坏值=缺失)
            if art is None or force or not bio_en_usable(art.bio):
                bio_en = (
                    enricher.generate_artist_bio(o.attributes)
                    if hasattr(enricher, "generate_artist_bio")
                    else None
                )
                bios = {}
                if bio_en:
                    bios["en"] = bio_en
                    for lang in target_langs:
                        if lang != "en":
                            try:
                                bios[lang] = translator.translate_section(bio_en, lang)
                            except Exception:
                                pass
                if art is None:
                    art = Artist(qid=aqid)
                    db.add(art)
                art.name_en = o.artist_en
                # 中文名缺(Wikidata 无 zh 标签)→ 翻译补,同标题机制
                name_zh = o.artist_zh
                if (
                    not name_zh
                    and o.artist_en
                    and hasattr(translator, "translate_section")
                ):
                    try:
                        name_zh = translator.translate_section(o.artist_en, "zh")
                    except Exception:
                        name_zh = None
                art.name_zh = name_zh
                try:
                    alabels = _wikidata_labels(aqid, target_langs)
                    art.name_i18n = _fill_i18n(
                        art.name_i18n, o.artist_en, alabels, target_langs, translator
                    )
                except Exception:
                    pass
                art.birth = af.get("artist_birth")
                art.death = af.get("artist_death")
                art.nationality = af.get("artist_nationality")
                art.notable_works = af.get("artist_notable_works")
                if bios:
                    art.bio = {**(art.bio or {}), **bios}  # 合并:保留其它语种,更新本次
                    # bio 变更 → 对应语言旧音频失效(下次点播放重生成)
                    ba = dict(art.bio_audio or {})
                    for _l in bios:
                        ba.pop(_l, None)
                    art.bio_audio = ba
                db.flush()
            # 国籍/代表作多语(交接③):缺语种才触网,幂等,失败不拖垮生成
            try:
                need = [
                    lang
                    for lang in target_langs
                    if not (art.nationality_i18n or {}).get(lang)
                    or not (art.notable_works_i18n or {}).get(lang)
                ]
                if need:
                    from app.services.enrichment.backfill import (
                        fill_artist_i18n_facts,
                    )

                    fill_artist_i18n_facts(
                        art,
                        target_langs,
                        translator,
                        _artist_i18n_facts(aqid, target_langs),
                    )
                    db.flush()
            except Exception:
                logger.exception("artist facts i18n failed: %s", aqid)
            # 已存在作者的 bio 语种补齐:en 有效、目标语言缺 → 纯翻译补
            # (作者实体全馆复用,老作者 bio 只有老语种;修 es/it 作者简介不全)
            bio_en = (art.bio or {}).get("en") if bio_en_usable(art.bio) else None
            if bio_en and hasattr(translator, "translate_section"):
                add = {}
                for lang in target_langs:
                    if lang != "en" and not (art.bio or {}).get(lang):
                        try:
                            add[lang] = translator.translate_section(bio_en, lang)
                        except Exception:
                            pass
                if add:
                    art.bio = {**(art.bio or {}), **add}
                    db.flush()

        if not o.title_zh and o.title_en and hasattr(translator, "translate_section"):
            try:
                o.title_zh = translator.translate_section(o.title_en, "zh")
                db.flush()
            except Exception:
                pass

    obj = _row_to_obj(o)
    material = build_material(obj)
    facts = _facts_text(obj)

    # 证据包:缺则建并落库(内容生成材料底座;阶段2 才切到它生成)。网络/LLM 抖动不拖垮。
    # Wikidata 富属性按 registry 门控:registry 在=真实生成(走网络);无=测试/离线(no-op,不触网)。
    if o.evidence_pack is None or force:
        from app.services.enrichment.evidence import build_evidence_pack

        ev_run_query = None if registry is not None else (lambda _sparql: [])
        try:
            o.evidence_pack = build_evidence_pack(
                {**obj, "qid": o.qid}, run_query=ev_run_query, complete=None
            )
            db.flush()
        except Exception:
            pass

    sections = sections_for(o.category)

    # 头条(默认讲解)先生成,作为模块去重锚:模块带着头条去重,避免与头条重复。
    guide_text = (
        enricher.generate_default_guide(obj, facts, guide_target_chars(o.popularity))
        if hasattr(enricher, "generate_default_guide")
        else None
    )

    en_published: dict = {}
    # 流式先出:guide 先 gate+落库(先于深度模块),前端轮询中途即可显示主讲解。
    if guide_text:
        gq = gate.check_section(material, facts, guide_text)
        persist_gated_sections(db, qid, "en", {"guide": gq}, model)
        if gq.status == "published" and gq.body:
            en_published["guide"] = gq.body
            o.content_status = "ready"
            db.flush()

    counts: dict = {}
    # ★ TTFC:请求语言的 guide 先翻先落——抢在 canonical/artist/qa 之前落库(每段
    # persist 即 commit),用户 ~15s 就看到自己语言的主讲解,而非等全件生成完。
    done_pr = None  # 已提前落库的 (lang, section),后面循环跳过避免重复翻译
    if lang_priority and lang_priority != "en" and "guide" in en_published:
        _title = ((o.attributes or {}).get("title_i18n") or {}).get(lang_priority)
        _titles = {lang_priority: _title} if _title else None
        # 作者译名一致性:锁作者卡规范名。全新作者此时 Artist 行未建(延后在
        # _enrich_artist_and_titles)→ glossary 缺,仅首件首语言 guide 有分叉风险(可接受,
        # 不为它把作者块拉回首屏关键路径)。
        from app.services.enrichment.backfill import artist_names_i18n

        _aname = artist_names_i18n(db, o).get(lang_priority)
        _artists_pr = {lang_priority: _aname} if _aname else None
        try:
            res = translator.translate_object(
                {"guide": en_published["guide"]},
                [lang_priority],
                titles=_titles,
                artists=_artists_pr,
            ).get(lang_priority, {})
            p, n = persist_gated_sections(db, qid, lang_priority, res, model)
            counts[lang_priority] = (p, n)
            done_pr = (lang_priority, "guide")
        except Exception:
            logger.exception("priority guide translate failed for %s", qid)

    # --- 以下延后:用户已见首屏,后台继续补全(作者实体/深度段/其余语言/问答)---
    _enrich_artist_and_titles()

    draft = enricher.generate_canonical(obj, sections, guide=guide_text)
    gated_en = gate.gate(material, facts, draft)
    pub_en, nr_en = persist_gated_sections(db, qid, "en", gated_en, model)
    if o.content_status != "ready":
        o.content_status = "ready" if pub_en > 0 else "empty"
    db.flush()
    counts["en"] = (pub_en, nr_en)

    en_published.update(
        {
            code: r.body
            for code, r in gated_en.items()
            if r.status == "published" and r.body
        }
    )

    # 作者译名一致性:作者块已跑完(_enrich_artist_and_titles),规范名齐 → 锁进翻译 glossary
    from app.services.enrichment.backfill import artist_names_i18n

    _anames = artist_names_i18n(db, o)

    # qa ‖ 翻译并行:两者都只读 en_published/material,互不依赖(实测 qa 24.9s 是最大后台
    # 单块,串行白排队)。线程里只跑纯 LLM(suggest 不碰 db),persist 留主线程(session 非
    # 线程安全)。同输入同调用集 → 不降质不增本;异常在 .result() 处按原语义抛出。
    qa_future = qa_pool = None
    if qa_suggester is not None:
        from concurrent.futures import ThreadPoolExecutor

        covered = "\n\n".join(v for v in en_published.values() if v)
        _qa_titles = {
            lg: ((o.attributes or {}).get("title_i18n") or {}).get(lg)
            for lg in target_langs
        }
        qa_pool = ThreadPoolExecutor(max_workers=1)
        qa_future = qa_pool.submit(
            qa_suggester.suggest,
            material,
            facts,
            o.category,
            target_langs,
            covered=covered,
            titles=_qa_titles,
            artists=_anames,
        )

    # 逐语言:翻完一门立即落库(懒生成场景用户尽早看到自己的语言);单语言失败不拖垮其他
    for lang in target_langs:
        if lang == "en":
            continue
        _title = ((o.attributes or {}).get("title_i18n") or {}).get(lang)
        _titles = {lang: _title} if _title else None
        _aname = _anames.get(lang)
        _artists = {lang: _aname} if _aname else None
        # 流式先出:guide 段先翻先落,请求语言用户先看到主讲解;其余段随后逐段落库。
        ordered = (["guide"] if "guide" in en_published else []) + [
            c for c in en_published if c != "guide"
        ]
        pub_total, nr_total = counts.get(lang, (0, 0))
        for code in ordered:
            if done_pr == (lang, code):
                continue  # 该段已在 TTFC 阶段提前落库,勿重复
            try:
                res = translator.translate_object(
                    {code: en_published[code]},
                    [lang],
                    titles=_titles,
                    artists=_artists,
                ).get(lang, {})
            except Exception:
                logger.exception("translate %s/%s failed for %s", lang, code, qid)
                continue
            p, n = persist_gated_sections(db, qid, lang, res, model)
            pub_total += p
            nr_total += n
        counts[lang] = (pub_total, nr_total)
    result = {"qid": qid, "counts": counts}
    if qa_future is not None:
        try:
            qa_by_lang = qa_future.result()
        finally:
            qa_pool.shutdown(wait=False)
        result["qa"] = {
            lang: persist_suggested_questions(db, qid, lang, items, model)
            for lang, items in qa_by_lang.items()
        }
    return result


def generate_museum(
    db,
    slug,
    *,
    enricher,
    gate,
    translator,
    target_langs,
    model,
    force=False,
    limit=None,
    qa_suggester=None,
    registry=None,
    country_lang=None,
) -> dict:
    """按馆批量：popularity 降序逐件 generate_object，聚合。"""
    m = db.query(Museum).filter_by(slug=slug).one_or_none()
    if not m:
        return {"slug": slug, "error": "unknown museum"}
    q = (
        db.query(MuseumObject)
        .filter_by(museum_id=m.id)
        .order_by(MuseumObject.popularity.desc())
    )
    if limit:
        q = q.limit(limit)
    results = [
        generate_object(
            db,
            o.qid,
            enricher=enricher,
            gate=gate,
            translator=translator,
            target_langs=target_langs,
            model=model,
            force=force,
            qa_suggester=qa_suggester,
            registry=registry,
            country_lang=country_lang,
        )
        for o in q.all()
    ]
    return {"slug": slug, "objects": len(results), "results": results}
