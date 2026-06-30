"""generate 编排：DB 对象 → 生成(2a) → 质量闸(2b) → 落英语 → 翻译(2c) → 按语言落库。
组件注入（enricher/gate/translator），整体离线可测。spec §7 / §17 三触发之一。"""

from __future__ import annotations

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

# 标"Creation year"消歧：避免 fact-consistency 判官把首展/收购/修复年误判为与创作年冲突。
_FACT_KEYS = [("Title", "title_en"), ("Artist", "artist_en"), ("Creation year", "year")]


def _artist_facts(qid):
    """薄包装：调结构化作者属性获取（测试 monkeypatch 此处避免触网）。"""
    from app.services.enrichment.material import fetch_artist_facts

    return fetch_artist_facts(qid)


def _row_to_obj(o) -> dict:
    """MuseumObject 行 → build_material/生成器吃的 obj dict。"""
    return {
        "title_en": o.title_en,
        "artist_en": o.artist_en,
        "year": o.year,
        "category": o.category,
        "attributes": o.attributes or {},
        "evidence_pack": getattr(o, "evidence_pack", None),
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
) -> dict:
    """单件：生成→质量闸→落英语→翻译→按语言落库。幂等跳过已发布英语（除非 force）。"""
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
        from app.services.enrichment.material import fetch_artist_material

        # ponytail: country_lang 暂硬编 fr，多馆从馆配置取
        # Wikidata/网络抖动不应拖垮整件生成 → 失败则当无作者材料继续
        try:
            artist_mat = fetch_artist_material(o.qid, registry, country_lang="fr")
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

    draft = enricher.generate_canonical(obj, sections, guide=guide_text)
    gated_en = gate.gate(material, facts, draft)
    pub_en, nr_en = persist_gated_sections(db, qid, "en", gated_en, model)
    o.content_status = "ready" if pub_en > 0 else "empty"
    db.flush()

    en_published = {
        code: r.body
        for code, r in gated_en.items()
        if r.status == "published" and r.body
    }
    # 默认讲解(单主线):上面已生成→三类闸→并入英语已发布集,随后随其它段统一翻译落库
    if guide_text:
        gq = gate.check_section(material, facts, guide_text)
        persist_gated_sections(db, qid, "en", {"guide": gq}, model)
        if gq.status == "published" and gq.body:
            en_published["guide"] = gq.body

    by_lang = translator.translate_object(en_published, target_langs)

    counts = {"en": (pub_en, nr_en)}
    for lang, results in by_lang.items():
        counts[lang] = persist_gated_sections(db, qid, lang, results, model)
    result = {"qid": qid, "counts": counts}
    if qa_suggester is not None:
        qa_by_lang = qa_suggester.suggest(material, facts, o.category, target_langs)
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
        )
        for o in q.all()
    ]
    return {"slug": slug, "objects": len(results), "results": results}
