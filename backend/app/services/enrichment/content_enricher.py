"""ContentEnricher：把事实 + Wikipedia 素材接地生成英语轴心分段讲解。
LLM 调用经注入的 complete 可调用，单测离线。"""

from __future__ import annotations

import json
import logging
import re

from app.services.enrichment.prompts import (
    build_artist_bio_prompt,
    build_default_guide_prompt,
    build_generation_prompt,
    build_material_probe_prompt,
)

logger = logging.getLogger(__name__)

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
    pack = obj.get("evidence_pack") or {}
    rich = [
        f for f in pack.get("facts", []) if f.get("source", "").startswith("wikidata:")
    ]
    if rich:
        lines.append("\n[STRUCTURED FACTS]")
        for f in rich:
            lines.append(f"- ({f.get('topic', '')}) {f.get('claim')}: {f.get('value')}")
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
    def __init__(self, complete, probe_complete=None):
        self._complete = complete  # complete(system, user) -> str
        # 料探针是**判定**不是创作 —— 必须走 temperature=0 的通道。
        # 生成通道是 0.3,拿它判定会让同一份材料重跑给出不同的"有没有料"
        # (实测 13.3% 不一致,见 default_complete 的 docstring)。
        # 缺省回落到 _complete 只为兼容老调用方/单测,生产由 factory 注入判定通道。
        self._probe_complete = probe_complete or complete

    def generate_canonical(
        self, obj: dict, sections: list[str], guide: str | None = None
    ) -> dict:
        """英语轴心：一次 LLM 调用产出请求段落。空串/未返回 → None（不发布）。"""
        material = build_material(obj)
        system, user = build_generation_prompt(
            material,
            sections,
            obj.get("category", "unknown"),
            guide=guide,
            popularity=obj.get("popularity"),
        )
        raw = self._complete(system, user)
        parsed = _parse_json(raw)
        out = {}
        for code in sections:
            v = parsed.get(code)
            out[code] = v.strip() if isinstance(v, str) and v.strip() else None
        return out

    def sections_with_material(self, obj: dict, sections: list[str]) -> list[str]:
        """料探针：剔掉材料撑不起的段，剩下的才生成。

        无料的段只有两条路——复述头条，或写"影响了无数艺术家"这类通论。
        两者都不该发布，所以宁可不写（契约：宁缺毋滥）。prod 实测(n=80)无料率
        analysis 40% / significance 77.5% / facts 41%。

        成本是**负的**：一次短判定，换掉那些段的生成 + 逐句接地闸。

        ⚠️ fail-open：探针出错就全量生成。判定挂了不该让内容凭空少一截。
        """
        from app.services.enrichment.category_config import MATERIAL_PROBE_LANES

        gated = [c for c in sections if c in MATERIAL_PROBE_LANES]
        if not gated:
            return sections
        try:
            system, user = build_material_probe_prompt(build_material(obj))
            probe = _parse_json(self._probe_complete(system, user))
        except Exception:
            logger.exception("material probe failed, generating all sections")
            return sections
        if not isinstance(probe, dict) or not probe:
            return sections
        kept = [
            c
            for c in sections
            if c not in MATERIAL_PROBE_LANES
            or probe.get(MATERIAL_PROBE_LANES[c]) is True
        ]
        dropped = [c for c in sections if c not in kept]
        if dropped:
            logger.info("material probe dropped sections: %s", ",".join(dropped))
        return kept

    def generate_artist_bio(self, artist_obj: dict) -> str | None:
        parts = [
            v for k, v in artist_obj.items() if k.startswith("artist_extract_") and v
        ]
        if not parts:
            return None
        material = "\n\n".join(parts)
        system, user = build_artist_bio_prompt(material)
        raw = self._complete(system, user)
        return raw.strip() if isinstance(raw, str) and raw.strip() else None

    def generate_default_guide(self, obj: dict, facts: str, target_chars) -> str | None:
        """单主线默认讲解(纯文本)。空串→None。"""
        material = build_material(obj)
        system, user = build_default_guide_prompt(material, facts, target_chars)
        raw = self._complete(system, user)
        text = raw.strip() if isinstance(raw, str) else ""
        return text or None


def default_complete(
    system: str,
    user: str,
    model: str = "gpt-4o-mini",
    channel: str = "misc",
    temperature: float = 0.3,
) -> str:
    """默认 LLM 调用（OpenAI，便宜模型）。grounded 生成是受约束改写，不需顶配。

    不强制 OpenAI 的 json_object 响应格式：JSON 类调用方（生成/质量闸/译文忠实）统一靠
    prompt「Return STRICT JSON」+ 容错解析 `_parse_json` 兜底，纯文本调用方（翻译段）也能用
    同一个 complete。json_object 模式会要求 messages 含 "json"，翻译 prompt 无此词会 400。
    channel=用量记账通路标签(成本工程①,factory 打标;缺省 misc)。

    temperature:**判定类调用必须传 0**(接地闸/忠实度闸)。判定是分类不是创作,同一段
    内容重跑该给同一个答案。默认 0.3 是给生成/翻译用的 —— 实测(2026-09-02,prod 英语
    问答 120+78 抽样)判定通道用 0.3 时,同一条内容三遍重跑有 **13.3%** 给出不一致的
    结论;换 0 后两遍一致率升到 **95%**。⚠️ 不是 100%:OpenAI 的 temperature=0 不保证
    确定性,所以**批量重判仍须多遍取交集**,别指望这个参数根治(契约纪律 21)。
    """
    import asyncio

    from app.services.content_generation_service import _get_openai_client

    # 成本可观测:强模型(非默认 mini)每次触发都打一条可 grep 日志(闸失败频率信号)
    # 统计: docker logs <backend> | grep -c 'STRONG_MODEL_USE'
    if model != "gpt-4o-mini":
        logger.info("STRONG_MODEL_USE model=%s", model)

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
            temperature=temperature,
        )
        u = getattr(resp, "usage", None)
        return resp.choices[0].message.content, u

    text, usage = asyncio.run(_run())
    from app.services.llm_usage import record_llm_usage

    record_llm_usage(
        channel,
        model,
        getattr(usage, "prompt_tokens", 0),
        getattr(usage, "completion_tokens", 0),
    )
    return text
