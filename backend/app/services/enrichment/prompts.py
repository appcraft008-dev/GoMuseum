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
