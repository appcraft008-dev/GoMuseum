"""ContentEnricher：把事实 + Wikipedia 素材接地生成英语轴心分段讲解。
LLM 调用经注入的 complete 可调用，单测离线。"""

from __future__ import annotations

import json
import re

from app.services.enrichment.prompts import build_generation_prompt

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


def _parse_json(text: str) -> dict:
    """容错解析模型返回的 JSON（去代码围栏 / 取首个 {...}）。"""
    t = text.strip()
    t = re.sub(r"^```(?:json)?|```$", "", t, flags=re.MULTILINE).strip()
    try:
        return json.loads(t)
    except Exception:
        m = re.search(r"\{.*\}", t, re.DOTALL)
        return json.loads(m.group(0)) if m else {}


class ContentEnricher:
    def __init__(self, complete):
        self._complete = complete  # complete(system, user) -> str

    def generate_canonical(self, obj: dict, sections: list[str]) -> dict:
        """英语轴心：一次 LLM 调用产出请求段落。空串/未返回 → None（不发布）。"""
        material = build_material(obj)
        system, user = build_generation_prompt(
            material, sections, obj.get("category", "unknown")
        )
        raw = self._complete(system, user)
        parsed = _parse_json(raw)
        out = {}
        for code in sections:
            v = parsed.get(code)
            out[code] = v.strip() if isinstance(v, str) and v.strip() else None
        return out
