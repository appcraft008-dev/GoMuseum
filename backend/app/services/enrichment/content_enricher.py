"""ContentEnricher：把事实 + Wikipedia 素材接地生成英语轴心分段讲解。
LLM 调用经注入的 complete 可调用，单测离线。"""

from __future__ import annotations

import json
import re

from app.services.enrichment.prompts import (
    build_default_guide_prompt,
    build_generation_prompt,
)

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
    "subjects_fr",
    "period_fr",
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
    artist_extracts = {
        k: v for k, v in attrs.items() if k.startswith("artist_extract_") and v
    }
    if artist_extracts:
        lines.append("\n[ABOUT THE ARTIST]")
        for k, v in artist_extracts.items():
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

    def generate_default_guide(self, obj: dict, facts: str, target_chars) -> str | None:
        """单主线默认讲解(纯文本)。空串→None。"""
        material = build_material(obj)
        system, user = build_default_guide_prompt(material, facts, target_chars)
        raw = self._complete(system, user)
        text = raw.strip() if isinstance(raw, str) else ""
        return text or None


def default_complete(system: str, user: str, model: str = "gpt-4o-mini") -> str:
    """默认 LLM 调用（OpenAI，便宜模型）。grounded 生成是受约束改写，不需顶配。

    不强制 OpenAI 的 json_object 响应格式：JSON 类调用方（生成/质量闸/译文忠实）统一靠
    prompt「Return STRICT JSON」+ 容错解析 `_parse_json` 兜底，纯文本调用方（翻译段）也能用
    同一个 complete。json_object 模式会要求 messages 含 "json"，翻译 prompt 无此词会 400。
    """
    import asyncio

    from app.services.content_generation_service import _get_openai_client

    client = _get_openai_client()
    if client is None:
        raise RuntimeError("OpenAI client 不可用")

    async def _run():
        resp = await client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            temperature=0.3,
        )
        return resp.choices[0].message.content

    return asyncio.run(_run())
