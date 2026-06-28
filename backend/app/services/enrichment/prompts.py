"""grounded 生成 prompt：只依据材料、类别感知、原创表达、缺料留空。"""

from __future__ import annotations

_SYSTEM = (
    "You are writing AUDIO-GUIDE narration for a museum visitor standing in front of the "
    "artwork — spoken, not an encyclopedia entry. Voice: vivid storytelling that makes dry "
    "facts come alive WITHOUT inventing anything (think a great popular-history narrator). "
    "Be colloquial and direct, speak to 'you', write people (artists, patrons) as real "
    "humans with motives, use a hook and gentle suspense, vary the rhythm. Each section has "
    "a ROLE and a target length given below; pick the single most engaging angle the "
    "material supports rather than summarizing everything; give one thing worth remembering.\n"
    "What you MAY write freely (these are NOT facts to be checked): framing and second-person "
    "guidance ('notice the red in the corner'), rhetorical questions, transitions, and GENTLE "
    "subjective impressions clearly phrased as impression ('the brushwork feels restless').\n"
    "What you MUST NOT do: invent any verifiable fact (names, dates, events, attributions, "
    "medium, what is depicted) that is not in the material. If the material is too thin for a "
    "section, return a SHORT honest text or an empty string — never pad with fabrication.\n"
    "Write in English. Return STRICT JSON mapping each requested section_code to its text "
    '(or "" if insufficient). No extra keys, no commentary.'
)


def build_generation_prompt(material: str, sections: list[str], category: str):
    from app.services.enrichment.category_config import section_role

    lines = []
    for code in sections:
        r = section_role(code)
        lines.append(
            f"- {code} — {r['role']} (aim ~{r['max_chars']} Chinese-char equivalent)"
        )
    roles_block = "\n".join(lines)
    user = (
        f"Artwork category: {category}\n"
        f"Write these sections (return JSON keyed by these exact codes):\n{roles_block}\n\n"
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
    "narrative BODY. List ONLY statements that DIRECTLY contradict a fact — asserting a "
    "different value for the SAME fact (e.g. a different artist, or a different creation "
    "date than the FACTS' year). Do NOT flag information the facts simply omit. In "
    "particular, a year tied to a DIFFERENT event (exhibition, acquisition, restoration, "
    "discovery) is NOT a conflict with the creation year — only flag a date when the body "
    "states a different value for the SAME fact. "
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


_QA_SYSTEM = (
    "You write 'curious visitor' question chips for ONE artwork, using ONLY the provided "
    "MATERIAL. The goal is to spark curiosity — NOT to quiz basic facts.\n"
    "Rules:\n"
    "1. NEVER ask about facts already shown on the wall label: title, artist, date/year, "
    "museum or location, medium, dimensions, inventory number. They are visible elsewhere, "
    "so asking them is useless noise.\n"
    "2. Ask what a curious visitor standing in front of the work would actually ask "
    "(why/how/who/what's the story): meaning, controversy, the people or scene depicted, "
    "technique, anecdotes, historical context.\n"
    "3. Grounded only: every answer must be fully supported by the material, no outside "
    "knowledge. Better to return FEWER questions (even an empty list) than to pad with "
    "trivia or unsupported claims.\n"
    "4. Each answer is 1-3 sentences: a satisfying hook in your own words, not copied from "
    "the material, and it should leave the visitor wanting to ask more.\n"
    "Write 0 to 4 such questions. "
    'Return STRICT JSON: {"qa": [{"question": "...", "answer": "..."}, ...]}. No commentary.'
)


def build_qa_prompt(material: str, category: str):
    user = f"Artwork category: {category}\n\nMATERIAL:\n{material}"
    return _QA_SYSTEM, user
