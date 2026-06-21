"""ContentTranslator：把英语轴心正文翻译到目标语言 + 译文忠实校验。
LLM 经注入式 complete，单测离线。spec §14 / §8A-5。"""

from __future__ import annotations

from app.services.enrichment.prompts import (
    build_faithfulness_prompt,
    build_translation_prompt,
)
from app.services.enrichment.quality import SectionQuality


def _parse():
    from app.services.enrichment.content_enricher import _parse_json

    return _parse_json


class ContentTranslator:
    def __init__(self, complete):
        self._complete = complete  # complete(system, user) -> str

    def translate_section(self, en_body: str, target_lang: str) -> str:
        system, user = build_translation_prompt(en_body, target_lang)
        return (self._complete(system, user) or "").strip()

    def check_faithfulness(self, en_body: str, translated: str, target_lang: str):
        system, user = build_faithfulness_prompt(en_body, translated, target_lang)
        data = _parse()(self._complete(system, user))
        return bool(data.get("faithful")), (data.get("issues") or [])
