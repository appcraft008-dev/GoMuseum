"""ContentTranslator：把英语轴心正文翻译到目标语言 + 译文忠实校验。
LLM 经注入式 complete，单测离线。spec §14 / §8A-5。"""

from __future__ import annotations

from app.services.enrichment.prompts import (
    build_faithfulness_prompt,
    build_name_translation_prompt,
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

    def translate_name(self, name: str, target_lang: str) -> str:
        """显示名(标题/人名)专用翻译:只返名字;剥模型仍套上的书名号/引号。"""
        system, user = build_name_translation_prompt(name, target_lang)
        out = (self._complete(system, user) or "").strip()
        return out.strip("《》\"'“”‘’«»")

    def check_faithfulness(self, en_body: str, translated: str, target_lang: str):
        system, user = build_faithfulness_prompt(en_body, translated, target_lang)
        data = _parse()(self._complete(system, user))
        return bool(data.get("faithful")), (data.get("issues") or [])

    def translate_object(self, en_sections: dict, target_langs: list[str]) -> dict:
        """把英语段落铺到目标语言。跳过 'en'（轴心不翻）与空 body 段。
        返回 {lang: {section_code: SectionQuality}}。"""
        out: dict = {}
        for lang in target_langs:
            if lang == "en":
                continue
            lang_result: dict = {}
            for code, en_body in en_sections.items():
                if not en_body:
                    continue
                translated = self.translate_section(en_body, lang)
                ok, issues = self.check_faithfulness(en_body, translated, lang)
                lang_result[code] = SectionQuality(
                    body=translated,
                    status="published" if ok else "needs_review",
                    grounding_ratio=1.0 if ok else 0.0,
                    conflicts=issues,
                    score=1.0 if ok else 0.0,
                )
            out[lang] = lang_result
        return out
