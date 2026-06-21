"""质量闸 QualityGate：逐句蕴含校验删不支持句 + 叙事/硬事实对账 + 质量分 → status。
LLM 判定经注入式 complete，单测离线。spec §8A-1/§8A-2。"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from app.services.enrichment.prompts import (
    build_entailment_prompt,
    build_fact_consistency_prompt,
)

GROUNDING_THRESHOLD = 0.6

_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+")


def _split_sentences(text: str | None) -> list[str]:
    """把正文切成句子列表（按 . ! ? 后接空白）。空/None → []。"""
    if not text or not text.strip():
        return []
    parts = _SENTENCE_SPLIT.split(text.strip())
    return [p.strip() for p in parts if p.strip()]


@dataclass
class SectionQuality:
    body: str | None
    status: str
    grounding_ratio: float
    conflicts: list[str] = field(default_factory=list)
    score: float = 0.0


def _parse():
    # 复用 Phase 2a 的容错解析，避免重复实现
    from app.services.enrichment.content_enricher import _parse_json

    return _parse_json


class QualityGate:
    def __init__(self, complete):
        self._complete = complete  # complete(system, user) -> str

    def check_section(self, material: str, facts: str, body: str) -> SectionQuality:
        parse = _parse()
        sentences = _split_sentences(body)
        if not sentences:
            return SectionQuality(body=None, status="needs_review", grounding_ratio=0.0)

        e_sys, e_user = build_entailment_prompt(material, sentences)
        verdicts = parse(self._complete(e_sys, e_user)).get("verdicts") or []
        kept = [s for s, ok in zip(sentences, verdicts) if ok is True]
        grounding_ratio = len(kept) / len(sentences)
        kept_body = " ".join(kept) if kept else None

        conflicts: list[str] = []
        if kept_body:
            f_sys, f_user = build_fact_consistency_prompt(facts, kept_body)
            conflicts = parse(self._complete(f_sys, f_user)).get("conflicts") or []

        score = grounding_ratio - (0.5 if conflicts else 0.0)
        score = max(0.0, score)
        published = (
            kept_body is not None
            and grounding_ratio >= GROUNDING_THRESHOLD
            and not conflicts
        )
        return SectionQuality(
            body=kept_body,
            status="published" if published else "needs_review",
            grounding_ratio=grounding_ratio,
            conflicts=conflicts,
            score=score,
        )

    def gate(self, material: str, facts: str, sections: dict) -> dict:
        """逐段过闸。sections 里 body 为 None/空的段视为 absent，跳过不进结果。
        返回 {section_code: SectionQuality}。"""
        results = {}
        for code, body in sections.items():
            if not body:
                continue
            results[code] = self.check_section(material, facts, body)
        return results
