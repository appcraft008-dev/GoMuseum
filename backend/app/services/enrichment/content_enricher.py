"""ContentEnricher：把事实 + Wikipedia 素材接地生成英语轴心分段讲解。
LLM 调用经注入的 complete 可调用，单测离线。"""

from __future__ import annotations

_FACT_FIELDS = [
    ("Title", "title_en"),
    ("Artist", "artist_en"),
    ("Year", "year"),
    ("Category", "category"),
]
_ATTR_FACT_KEYS = [
    "medium_fr",
    "dimensions",
    "inventory_number",
    "provenance_fr",
    "exhibitions_fr",
    "bibliography_fr",
    "title_fr",
    "artist_fr",
]


def build_material(obj: dict) -> str:
    """组装"材料包"文本（结构化事实 + Wikipedia 正文），每条标来源，供 grounded 生成。"""
    lines = ["[FACTS]"]
    for label, key in _FACT_FIELDS:
        v = obj.get(key)
        if v:
            lines.append(f"- {label}: {v}")
    attrs = obj.get("attributes") or {}
    for key in _ATTR_FACT_KEYS:
        v = attrs.get(key)
        if v:
            lines.append(f"- {key}: {v}")
    extracts = {k: v for k, v in attrs.items() if k.startswith("extract_") and v}
    if extracts:
        lines.append("\n[WIKIPEDIA EXTRACTS]")
        for k, v in extracts.items():
            lines.append(f"({k}) {v}")
    return "\n".join(lines)
