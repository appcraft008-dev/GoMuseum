"""质量闸 QualityGate：逐句蕴含校验删不支持句 + 叙事/硬事实对账 + 质量分 → status。
LLM 判定经注入式 complete，单测离线。spec §8A-1/§8A-2。"""

from __future__ import annotations

import re

GROUNDING_THRESHOLD = 0.6

_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+")


def _split_sentences(text: str | None) -> list[str]:
    """把正文切成句子列表（按 . ! ? 后接空白）。空/None → []。"""
    if not text or not text.strip():
        return []
    parts = _SENTENCE_SPLIT.split(text.strip())
    return [p.strip() for p in parts if p.strip()]
