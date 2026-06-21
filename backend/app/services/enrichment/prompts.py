"""grounded 生成 prompt：只依据材料、类别感知、原创表达、缺料留空。"""

from __future__ import annotations

_SYSTEM = (
    "You are a museum content writer. Write section-by-section explanations of an artwork "
    "USING ONLY the provided material (facts + encyclopedia extracts). "
    "Rules: (1) Use only information present in the material; do NOT add facts from your own "
    "knowledge. (2) Write in your own original wording; do NOT copy source sentences. "
    "(3) If the material lacks enough for a section, return an empty string for that section "
    "(better empty than fabricated). (4) Be accurate, concise, engaging. "
    "Return STRICT JSON: an object mapping each requested section_code to its English text "
    '(or "" if insufficient). No extra keys, no commentary.'
)


def build_generation_prompt(material: str, sections: list[str], category: str):
    user = (
        f"Artwork category: {category}\n"
        f"Write these sections (return JSON keyed by these exact codes): {sections}\n\n"
        f"Material:\n{material}"
    )
    return _SYSTEM, user


_ENTAILMENT_SYSTEM = (
    "You are a fact-checking judge. You are given source MATERIAL and a numbered list of "
    "SENTENCES taken from an artwork explanation. For EACH sentence decide whether it is "
    "entailed (fully supported) by the material. Judge USING ONLY the material; a sentence "
    "that adds any fact not present in the material is NOT supported, even if it is true in "
    'the real world. Return STRICT JSON: {"verdicts": [true, false, ...]} with one boolean '
    "per sentence in the SAME order. No commentary."
)


def build_entailment_prompt(material: str, sentences: list[str]):
    numbered = "\n".join(f"{i + 1}. {s}" for i, s in enumerate(sentences))
    user = f"MATERIAL:\n{material}\n\nSENTENCES:\n{numbered}"
    return _ENTAILMENT_SYSTEM, user


_FACT_CONSISTENCY_SYSTEM = (
    "You are a fact-checking judge. You are given structured FACTS about an artwork and a "
    "narrative BODY. List every statement in the body that CONTRADICTS the facts (e.g. wrong "
    "year, wrong artist, wrong dimensions). Ignore extra detail that does not contradict. "
    'Return STRICT JSON: {"conflicts": ["...", ...]} (empty list if none). No commentary.'
)


def build_fact_consistency_prompt(facts: str, body: str):
    user = f"FACTS:\n{facts}\n\nBODY:\n{body}"
    return _FACT_CONSISTENCY_SYSTEM, user


from app.services.enrichment.lang_config import LANG_NAMES

_TRANSLATION_SYSTEM = (
    "You are a professional art translator. Translate the given English artwork explanation "
    "into {lang}. Rules: (1) Be FAITHFUL — do NOT add, remove, or alter any fact. "
    "(2) Keep proper names, artist names, and work TITLES in their original form or the "
    "established exonym in the target language; do NOT literally translate titles. "
    "(3) Natural, fluent {lang}. Return ONLY the translated text, no commentary, no quotes."
)


def build_translation_prompt(en_body: str, target_lang: str):
    lang = LANG_NAMES.get(target_lang, target_lang)
    system = _TRANSLATION_SYSTEM.format(lang=lang)
    user = f"English:\n{en_body}"
    return system, user


_FAITHFULNESS_SYSTEM = (
    "You are a translation quality judge. You are given an English SOURCE and its {lang} "
    "TRANSLATION. Decide whether the translation is faithful: it must convey exactly the "
    "same facts with nothing added and nothing omitted (wording/fluency differences are "
    'fine). Return STRICT JSON: {{"faithful": true|false, "issues": ["..."]}} '
    "(issues empty if faithful). No commentary."
)


def build_faithfulness_prompt(en_body: str, translated: str, target_lang: str):
    lang = LANG_NAMES.get(target_lang, target_lang)
    system = _FAITHFULNESS_SYSTEM.format(lang=lang)
    user = f"SOURCE (English):\n{en_body}\n\nTRANSLATION ({lang}):\n{translated}"
    return system, user
