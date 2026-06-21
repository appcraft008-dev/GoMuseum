"""generate 编排：DB 对象 → 生成(2a) → 质量闸(2b) → 落英语 → 翻译(2c) → 按语言落库。
组件注入（enricher/gate/translator），整体离线可测。spec §7 / §17 三触发之一。"""

from __future__ import annotations

from app.models.content import ObjectContentSection
from app.models.museum_object import MuseumObject
from app.services.content_repo import persist_gated_sections
from app.services.enrichment.category_config import sections_for
from app.services.enrichment.content_enricher import build_material

_FACT_KEYS = [("Title", "title_en"), ("Artist", "artist_en"), ("Year", "year")]


def _row_to_obj(o) -> dict:
    """MuseumObject 行 → build_material/生成器吃的 obj dict。"""
    return {
        "title_en": o.title_en,
        "artist_en": o.artist_en,
        "year": o.year,
        "category": o.category,
        "attributes": o.attributes or {},
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
    db, qid, *, enricher, gate, translator, target_langs, model, force=False
) -> dict:
    """单件：生成→质量闸→落英语→翻译→按语言落库。幂等跳过已发布英语（除非 force）。"""
    o = db.query(MuseumObject).filter_by(qid=qid).one_or_none()
    if not o:
        return {"qid": qid, "skipped": "absent"}
    if not force and _has_published_en(db, o.id):
        return {"qid": qid, "skipped": "exists"}

    obj = _row_to_obj(o)
    material = build_material(obj)
    facts = _facts_text(obj)
    sections = sections_for(o.category)

    draft = enricher.generate_canonical(obj, sections)
    gated_en = gate.gate(material, facts, draft)
    pub_en, nr_en = persist_gated_sections(db, qid, "en", gated_en, model)

    en_published = {
        code: r.body
        for code, r in gated_en.items()
        if r.status == "published" and r.body
    }
    by_lang = translator.translate_object(en_published, target_langs)

    counts = {"en": (pub_en, nr_en)}
    for lang, results in by_lang.items():
        counts[lang] = persist_gated_sections(db, qid, lang, results, model)
    return {"qid": qid, "counts": counts}
