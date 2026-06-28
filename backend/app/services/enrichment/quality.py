"""质量闸 QualityGate：逐句蕴含校验删不支持句 + 叙事/硬事实对账 + 质量分 → status。
LLM 判定经注入式 complete，单测离线。spec §8A-1/§8A-2。"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from app.services.enrichment.prompts import build_entailment_prompt

# 存活率阈值：三类闸下 keep 含引导句/解读句（仅无据事实主张被删），
# 低存活率意味着大量事实性主张无材料支持（料薄/脑补），需人工复审。
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
        """接地闸（三类判定）：逐句送蕴含模型，按 verdicts 保留/删除各句，
        计算存活率(survival rate) = kept/total，≥ GROUNDING_THRESHOLD → published。

        三类判定语义（接地闸返回 true=keep）：
          - 事实硬接地：材料直接支持的事实句 → keep=True
          - 引导句/观察句：引导观众感知、无具体可证伪事实 → keep=True（不占"无据名额"）
          - 解读句：主观/情感诠释 → keep=True（同上）
          - 无据事实主张：涉具体事实但材料不支持 → keep=False（被删）

        因此低存活率 = 大量事实性主张无材料支持（料薄/脑补） → needs_review；
        新语义下引导/解读句天然留存，存活率比纯事实模式更高，阈值语义不变。

        不再做阻塞性 fact-consistency 对账——它对 Joconde 富材料里的事件年(展出/收购)
        高频误报、误杀已接地内容(2026-06-21 prod 金丝雀诊断：grounding=1.0 的段被年份
        误判杀掉)，且其目标(错年份/错作者)已被蕴含覆盖(材料不支持→会被删)。
        `facts` 入参保留以兼容调用方签名。fact-consistency prompt 仍在 prompts.py 备用。
        """
        parse = _parse()
        sentences = _split_sentences(body)
        if not sentences:
            return SectionQuality(body=None, status="needs_review", grounding_ratio=0.0)

        e_sys, e_user = build_entailment_prompt(material, sentences)
        verdicts = parse(self._complete(e_sys, e_user)).get("verdicts") or []
        kept = [s for s, ok in zip(sentences, verdicts) if ok is True]
        grounding_ratio = len(kept) / len(sentences)
        kept_body = " ".join(kept) if kept else None

        published = kept_body is not None and grounding_ratio >= GROUNDING_THRESHOLD
        return SectionQuality(
            body=kept_body,
            status="published" if published else "needs_review",
            grounding_ratio=grounding_ratio,
            conflicts=[],
            score=grounding_ratio,
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
