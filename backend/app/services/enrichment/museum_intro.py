"""博物馆介绍 + 封面(spec 2026-07-18)。
介绍:qid→en extract→接地生成(gate 不过不落)→按语言补缺(完整性按语言维度)。
封面:top-N 有图件逐件 LLM 得体性判定(古典/宗教裸体可,写实露骨否决;判定失败保守跳过)。
门面类预生成内容(成本分界原则),每馆一次性几分钱。"""

from __future__ import annotations

import logging

from app.models.museum import Museum
from app.models.museum_object import MuseumObject, ObjectImage
from app.services.enrichment.content_enricher import _parse_json
from app.services.enrichment.material import fetch_museum_intro_material
from app.services.enrichment.prompts import (
    build_cover_safety_prompt,
    build_museum_intro_prompt,
)

logger = logging.getLogger(__name__)


def generate_museum_intro(
    db,
    slug: str,
    *,
    complete,
    gate,
    translator,
    langs: list,
    force: bool = False,
    fetch_material=None,
) -> dict:
    m = db.query(Museum).filter_by(slug=slug).one_or_none()
    if not m:
        return {"error": "unknown museum"}
    di = {} if force else dict(m.description_i18n or {})
    out = {"generated": False, "translated": [], "skipped": None}

    if not di.get("en"):
        mat = (fetch_material or fetch_museum_intro_material)(m.qid)
        extract = mat.get("extract_en")
        if not extract:
            out["skipped"] = "no_material"  # 宁缺毋滥:源薄不硬写
            return out
        system, user = build_museum_intro_prompt(m.name_en or slug, extract)
        text = (complete(system, user) or "").strip()
        q = gate.check_section(extract, f"- Museum: {m.name_en}", text)
        if q.status != "published" or not q.body:
            return out  # gate 不过=不落库,重跑再试(无 needs_review 状态机)
        di["en"] = q.body
        out["generated"] = True

    for lang in langs:  # 按语言补缺:已有语种不动,缺的从 en 轴心纯翻译
        if lang == "en" or di.get(lang):
            continue
        try:
            di[lang] = translator.translate_section(di["en"], lang)
            out["translated"].append(lang)
        except Exception:
            logger.exception("museum intro translate %s failed: %s", lang, slug)
    m.description_i18n = di
    db.flush()
    return out


def select_cover(db, slug: str, *, complete, force: bool = False, limit: int = 10):
    """top-N 热度有图件里选第一张过得体性判定的当封面;全不过→None(前端隐藏)。"""
    m = db.query(Museum).filter_by(slug=slug).one_or_none()
    if not m:
        return None
    if m.cover_image_key and not force:
        return m.cover_image_key
    rows = (
        db.query(MuseumObject, ObjectImage)
        .join(ObjectImage, ObjectImage.object_id == MuseumObject.id)
        .filter(
            MuseumObject.museum_id == m.id,
            ObjectImage.role == "primary",
            ObjectImage.image_key.isnot(None),
        )
        .order_by(MuseumObject.popularity.desc().nullslast())
        .limit(limit)
        .all()
    )
    for o, img in rows:
        system, user = build_cover_safety_prompt(
            o.title_en or o.qid, o.artist_en, o.category
        )
        try:
            ok = bool(_parse_json(complete(system, user)).get("appropriate"))
        except Exception:  # 判定失败=保守跳过该件(封面宁缺毋错)
            logger.warning("cover judge failed for %s, skip", o.qid)
            continue
        if ok:
            m.cover_image_key = img.image_key
            db.flush()
            return img.image_key
    return None
