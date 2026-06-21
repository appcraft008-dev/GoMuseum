"""generate 编排：DB 对象 → 生成(2a) → 质量闸(2b) → 落英语 → 翻译(2c) → 按语言落库。
组件注入（enricher/gate/translator），整体离线可测。spec §7 / §17 三触发之一。"""

from __future__ import annotations

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
