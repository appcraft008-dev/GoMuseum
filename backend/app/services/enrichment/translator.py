"""ContentTranslator：把英语轴心正文翻译到目标语言 + 译文忠实校验。
LLM 经注入式 complete，单测离线。spec §14 / §8A-5。"""

from __future__ import annotations

import re

from app.services.enrichment.lang_config import strip_language_label
from app.services.enrichment.prompts import (
    build_faithfulness_prompt,
    build_name_translation_prompt,
    build_translation_prompt,
)
from app.services.enrichment.quality import SectionQuality

_NAME_QUOTES = "《》\"'“”‘’«»"

# 规范名注入用的 XML 标签(prompts.build_translation_prompt),偶尔被模型抄进译文。
_CANONICAL_TAG = re.compile(r"</?canonical_(?:title|artist|museum)>")


def strip_name(text: str) -> str:
    """剥模型套上的书名号/引号(translate_name 与 batch 回填共用)。"""
    return (text or "").strip().strip(_NAME_QUOTES)


def _parse():
    from app.services.enrichment.content_enricher import _parse_json

    return _parse_json


# 非拉丁字母的目标语言里,正文夹着的**小写**拉丁词就是漏译:
# 「背景中华丽的 urn 和宏伟的柱子」「构图经过精心安排, reclining 的塞内卡位于中心」
# (2026-09-13 第一批 10 件实测,2 处,都在同一件)。
# 大写开头的放过 —— 那是人名/地名/作品原名,刻意保留的。引号与书名号内的内容
# 整段挖掉再扫,同理:《Têtes d'enfants》这种保留的原名不该算漏译。
# 两道闸都抓不到它:忠实度闸看事实(没漏事实),语言检测看整段语种(99% 是中文,判过)。
_NON_LATIN_LANGS = {"zh", "zh-hant", "ja", "ko"}
_QUOTED = re.compile(r"《[^》]*》|“[^”]*”|\"[^\"]*\"|'[^']*'|‘[^’]*’|「[^」]*」")
_LOWER_LATIN_WORD = re.compile(r"(?<![A-Za-z])[a-z]{3,}(?![A-Za-z])")


def untranslated_words(text: str, lang: str) -> list[str]:
    """译文里漏翻的英文词。非拉丁语种才有意义,其余语言返回空。"""
    if lang not in _NON_LATIN_LANGS:
        return []
    return _LOWER_LATIN_WORD.findall(_QUOTED.sub(" ", text or ""))


def _lang_ok(text, lang):
    from app.services.enrichment.lang_detect import text_in_language

    return text_in_language(text, lang) and not untranslated_words(text, lang)


class ContentTranslator:
    def __init__(self, complete, complete_strong=None, complete_judge=None):
        self._complete = complete  # complete(system, user) -> str (默认 gpt-4o-mini)
        # 闸失败时的强模型重译(gpt-4o);语言无关,靠闸信号触发(不硬编语言名单)
        self._complete_strong = complete_strong
        # 忠实度**判定**专用(temperature=0)。翻译要创作、判定要复现,共用一个
        # complete 会把判定也带上随机性 —— 同一条译文重跑给不同结论,存量因此
        # 积压误判(2026-09-02 实测)。缺省回退 _complete,老调用方行为不变。
        self._complete_judge = complete_judge or complete

    def translate_section(
        self,
        en_body: str,
        target_lang: str,
        *,
        strong=False,
        title=None,
        artist=None,
        museum=None,
    ) -> str:
        system, user = build_translation_prompt(
            en_body, target_lang, title, artist, museum
        )
        fn = (
            self._complete_strong
            if (strong and self._complete_strong)
            else self._complete
        )
        # 剥掉模型回贴的语言标签 —— 根因已在 prompt 侧修掉(不再用「语言名: 内容」
        # 的格式示范),这里是兜底:形式缺陷两道闸都抓不到(忠实度看事实、
        # 语言检测看语种),漏出去就是 1088 段那样的存量。
        # 同理再剥 <canonical_*> 标签:规范名改用标签注入后(见 prompts.py 注释),
        # A/B 5×6 里韩语有 1 次把标签原样抄进了译文。发生率低,但漏出去是正文里
        # 明晃晃的 XML —— 比一个错引号糟得多,而两道闸同样看不见。
        out = strip_language_label((fn(system, user) or "").strip())
        return _CANONICAL_TAG.sub("", out).strip()

    def translate_name(self, name: str, target_lang: str) -> str:
        """显示名(标题/人名)专用翻译:只返名字;剥模型仍套上的书名号/引号。
        名字短/便宜 → 有强模型(gpt-4o)就用它(音译/无残片质量远好于 mini)。"""
        system, user = build_name_translation_prompt(name, target_lang)
        fn = self._complete_strong or self._complete
        return strip_name(fn(system, user))

    def check_faithfulness(
        self,
        en_body: str,
        translated: str,
        target_lang: str,
        title: str | None = None,
        artist: str | None = None,
    ):
        system, user = build_faithfulness_prompt(
            en_body, translated, target_lang, title, artist
        )
        data = _parse()(self._complete_judge(system, user))
        return bool(data.get("faithful")), (data.get("issues") or [])

    def translate_object(
        self,
        en_sections: dict,
        target_langs: list[str],
        titles: dict | None = None,
        artists: dict | None = None,
    ) -> dict:
        """把英语段落铺到目标语言。跳过 'en'（轴心不翻）与空 body 段。
        titles={lang: 规范标题}:正文引用标题统一用显示名(消除分叉)。
        artists={lang: 作者规范名}:正文称呼作者统一用作者卡译名(消除音译分叉)。
        返回 {lang: {section_code: SectionQuality}}。"""
        titles = titles or {}
        artists = artists or {}
        out: dict = {}
        for lang in target_langs:
            if lang == "en":
                continue
            title = titles.get(lang)
            artist = artists.get(lang)
            lang_result: dict = {}
            for code, en_body in en_sections.items():
                if not en_body:
                    continue
                translated = self.translate_section(
                    en_body, lang, title=title, artist=artist
                )
                ok, issues = self.check_faithfulness(
                    en_body, translated, lang, title, artist
                )
                lang_ok = _lang_ok(translated, lang)
                if (not ok or not lang_ok) and self._complete_strong:
                    # 不忠实 或 语言不符 → 强模型(gpt-4o)重译一次并采用
                    # (总比 mini 的坏译好;顽固少数才付费,语言无关靠闸信号触发)
                    translated = self.translate_section(
                        en_body, lang, strong=True, title=title, artist=artist
                    )
                    ok, issues = self.check_faithfulness(
                        en_body, translated, lang, title, artist
                    )
                    lang_ok = _lang_ok(translated, lang)
                published = ok and lang_ok  # 忠实且语言正确才发布
                lang_result[code] = SectionQuality(
                    body=translated,
                    status="published" if published else "needs_review",
                    grounding_ratio=1.0 if published else 0.0,
                    conflicts=issues if lang_ok else (issues + ["language_mismatch"]),
                    score=1.0 if published else 0.0,
                )
            out[lang] = lang_result
        return out
