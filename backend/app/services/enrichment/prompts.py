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


def build_generation_prompt(
    material: str,
    sections: list[str],
    category: str,
    guide: str | None = None,
    popularity: int | None = None,
):
    from app.services.enrichment.category_config import (
        section_role,
        section_target_chars,
    )

    lines = []
    for code in sections:
        r = section_role(code)
        aim = section_target_chars(code, popularity)
        lines.append(f"- {code} — {r['role']} (aim ~{aim} Chinese-char equivalent)")
    roles_block = "\n".join(lines)
    guide_block = (
        f'\nThe visitor ALREADY heard this HEADLINE guide:\n"""\n{guide}\n"""\n'
        "Each section must go DEEPER on ITS OWN lane and add NEW material the headline did "
        "NOT cover. Do NOT repeat the headline or other sections. If a section would only "
        "repeat what's already said, return an empty string for it.\n"
        if guide
        else ""
    )
    user = (
        f"Artwork category: {category}\n"
        f"Write these sections (return JSON keyed by these exact codes), each staying strictly "
        f"in its lane. Go DEEPER by unpacking concrete facts and details FROM THE MATERIAL — "
        f"never pad or dilute with generic filler:\n{roles_block}\n{guide_block}\n"
        f"Material (facts tagged with their lane topic):\n{material}"
    )
    return _SYSTEM, user


_ENTAILMENT_SYSTEM = (
    "You are a grounding judge for audio-guide narration. Given source MATERIAL and a "
    "numbered list of SENTENCES, decide for EACH sentence whether to KEEP it (true) or "
    "REMOVE it (false), by its type:\n"
    "- FACTUAL CLAIM (a checkable fact about the work/artist/history: a name, date, medium, "
    "event, attribution, or what is depicted) → KEEP only if fully supported by the "
    "material; otherwise REMOVE. A claim true in the real world but absent from the material "
    "is still REMOVE.\n"
    "- FRAMING / GUIDANCE (second-person direction like 'notice the corner', rhetorical "
    "questions, transitions, sensory pointers) → KEEP. These make no factual claim.\n"
    "- IMPRESSION (a gentle subjective reading like 'the brushwork feels restless') → KEEP, "
    "UNLESS it asserts or implies a specific fact not in the material, or contradicts the "
    "material → then REMOVE.\n"
    "When in doubt whether something is a factual claim, treat it AS a factual claim and "
    "require support (bias toward grounding).\n"
    'Return STRICT JSON: {"verdicts": [true, false, ...]} with one boolean per sentence in '
    "the SAME order (true = keep). No commentary."
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
    "(1b) Render EVERY word in {lang}. NEVER leave source-language (English) fragments "
    'untranslated mid-sentence (e.g. common nouns/phrases like "severed head", '
    '"still life" must become their {lang} equivalents). This is critical for languages '
    "distant from English (Chinese, Japanese, Korean) where copying is not an option. "
    "(2) For people/places/work TITLES: when an established {lang} form (exonym) exists, "
    "USE IT (e.g. Salome→\u838e\u4e50\u7f8e, Gustave Moreau→\u53e4\u65af\u5854\u592b\u00b7\u83ab\u7f57 in Chinese); only keep the "
    "original form when no established {lang} form exists. Be CONSISTENT across the whole "
    "text (same name → same rendering everywhere). Do NOT literally/word-for-word translate "
    "titles that have a conventional {lang} title. "
    "(3) Natural, fluent {lang}. (4) PRESERVE THE TONE — keep the engaging, spoken, "
    "second-person audio-guide voice, hooks and gentle wit; convey them idiomatically in "
    "{lang} rather than translating jokes literally. "
    "Return ONLY the translated text, no commentary, no quotes."
)


def build_translation_prompt(
    en_body: str,
    target_lang: str,
    title: str | None = None,
    artist: str | None = None,
):
    lang = LANG_NAMES.get(target_lang, target_lang)
    system = _TRANSLATION_SYSTEM.format(lang=lang)
    if title:
        # 标题真相唯一化:正文引用标题一律用显示名(消除内容翻译自选译名的分叉)
        system += (
            f" IMPORTANT: this artwork's canonical {lang} title is 「{title}」 — "
            f"whenever the text refers to the work by name, use EXACTLY this title, "
            f"do not invent an alternative rendering."
        )
    if artist:
        # 作者译名一致性(标题真相唯一化的姊妹):正文称呼作者一律用作者卡规范名
        # (消除音译分叉,如 Seurat 修拉/秀拉——正文与 artists.name_i18n 统一)
        system += (
            f" IMPORTANT: the artist's canonical {lang} name is 「{artist}」 — "
            f"whenever the text refers to the artist by name, use EXACTLY this "
            f"rendering, do not use any alternative transliteration."
        )
    user = f"English:\n{en_body}"
    return system, user


_NAME_TRANSLATION_SYSTEM = (
    "You translate museum artwork titles and artist names into {lang}. "
    "Return ONLY the name itself — no quotes, no brackets, no 《》, no commentary. "
    "Rules: (a) Render EVERY word in {lang}; NEVER leave source-language (English) "
    'fragments (e.g. "Reclining Nude" must be fully rendered, not "卧 Nude"). '
    "(b) Use the STANDARD/conventional {lang} form: established exonym for artist names, "
    "conventional title for well-known works, standard transliteration for names "
    "(e.g. Olympia → the standard {lang} transliteration, not an ad-hoc one). "
    "(c) For descriptive titles, translate the meaning. Only keep the original form "
    "when it is a proper noun with genuinely no {lang} form."
)


def build_name_translation_prompt(name: str, target_lang: str):
    lang = LANG_NAMES.get(target_lang, target_lang)
    return _NAME_TRANSLATION_SYSTEM.format(lang=lang), f"Name:\n{name}"


_FAITHFULNESS_SYSTEM = (
    "You are a translation quality judge. You are given an English SOURCE and its {lang} "
    "TRANSLATION. Decide whether the translation is faithful: it must convey exactly the "
    "same facts with nothing added and nothing omitted (wording/fluency differences are "
    "fine). ALSO mark it UNFAITHFUL if the TRANSLATION still contains any untranslated "
    "source-language (English) words or phrases that should have been rendered in {lang} "
    '(e.g. a common noun like "nude" or "severed head" left in English mid-text). '
    "EXCEPTION: proper nouns (people/places) and work TITLES kept in their conventional "
    "original/exonym form are fine and must NOT be flagged. "
    'Return STRICT JSON: {{"faithful": true|false, "issues": ["..."]}} '
    "(issues empty if faithful). No commentary."
)


def build_faithfulness_prompt(en_body: str, translated: str, target_lang: str):
    lang = LANG_NAMES.get(target_lang, target_lang)
    system = _FAITHFULNESS_SYSTEM.format(lang=lang)
    user = f"SOURCE (English):\n{en_body}\n\nTRANSLATION ({lang}):\n{translated}"
    return system, user


_QA_SYSTEM = (
    "You write 'curious visitor' question chips for ONE artwork, using ONLY the provided "
    "MATERIAL. WRITE IN ENGLISH (both question and answer) — this is the English axis; other "
    "languages are translated later. The guide and modules ALREADY explain the work's MAIN "
    "themes (its meaning, the controversy, the technique, the key symbols). Your job is the "
    "OPPOSITE: surface the peripheral 'huh, I didn't know that' angles those did NOT cover.\n"
    "Rules:\n"
    "1. NEVER ask about wall-label facts (title, artist, date/year, museum/location, medium, "
    "dimensions, inventory) — useless noise.\n"
    "2. Cast a WIDE net for angles NOT already told: a person's surprising backstory, a hidden "
    "or easily-missed detail, the people/place depicted, the work's afterlife (theft, hiding, "
    "restoration, later influence, where it travelled), the artist's connection to it, a "
    "technical or material curiosity, a comparison or reference — any fresh, grounded angle. Do "
    "NOT re-ask the main meaning / controversy / the same symbols the guide already explained.\n"
    "3. When an ALREADY-COVERED block is provided, its topics are FORBIDDEN: any question whose "
    "answer is already in it is rejected. Exhaust the peripheral angles above to reach the count; "
    "drop below the minimum ONLY if the material truly offers nothing more — never pad by "
    "re-asking a covered theme.\n"
    "4. Grounded only: every answer fully supported by the material, no outside knowledge.\n"
    "5. FORMAT (strict): `question` MUST be ONE short, genuine interrogative sentence ending in "
    "'?' — nothing after the '?', no statement or description appended. Put ALL the substance / "
    "explanation in `answer` (1-3 sentences, your own words, a satisfying hook). A declarative "
    "sentence in the `question` field, or content trailing after the '?', is WRONG. Example — "
    'GOOD: {"question": "Why did Van Gogh use so much blue and yellow here?", "answer": "In his '
    'letters he wrote that the night is richer in colour than the day..."}. '
    'BAD: question = "Interestingly, the couple in the foreground symbolises love..." '
    "(a statement, no question mark).\n"
    "Write 2 to 4 such questions (aim for 3); fewer only if the material genuinely can't support more. "
    'Return STRICT JSON: {"qa": [{"question": "...", "answer": "..."}, ...]}. No commentary.'
)


def build_qa_prompt(material: str, category: str, covered: str | None = None):
    covered_block = (
        "\n\nALREADY COVERED (guide + modules) — these topics are FORBIDDEN; any question whose "
        "answer is already in here will be rejected. Ask ONLY genuinely new / peripheral angles, "
        "or return fewer:\n"
        f'"""\n{covered}\n"""'
        if covered
        else ""
    )
    user = f"Artwork category: {category}{covered_block}\n\nMATERIAL:\n{material}"
    return _QA_SYSTEM, user


_ARTIST_BIO_SYSTEM = (
    "You write a concise, engaging biography of an ARTIST (the maker), using ONLY the MATERIAL. "
    "Cover: who they were, their life and character, what drove them, their place in art history. "
    "Write in ENGLISH (regardless of the material's language), plain prose, no headings. "
    "⚠️ The MATERIAL is often in French — you MUST still write entirely in ENGLISH; "
    "never copy French sentences or phrases verbatim. "
    "~200-300 Chinese-char equivalent in length. Grounded only, no fabrication."
)


def build_artist_bio_prompt(material: str):
    return _ARTIST_BIO_SYSTEM, f"MATERIAL (about the artist):\n{material}"


_DEFAULT_GUIDE_SYSTEM = (
    "You are a museum audio-guide writer. Write ONE short spoken on-site guide for a visitor "
    "standing in front of the artwork, built around a SINGLE core point (one throughline) — "
    "not a summary of everything. Structure (5 beats, flowing, not labeled): "
    "(1) a hook that gets them looking; (2) guide them to NOTICE 1-2 concrete details; "
    "(3) explain why those details matter; (4) add only the necessary background; "
    "(5) end on a memory point or an open question. "
    "Voice: colloquial, second-person, vivid storytelling that makes facts come alive "
    "(a great popular-history narrator). You MAY freely use framing/second-person guidance "
    "and gentle impressions clearly phrased as impression. You MUST NOT invent verifiable "
    "facts (names, dates, events, attributions, medium, what is depicted) not in the material. "
    "This is the HEADLINE; deep modules cover the rest, so DON'T try to cover everything. "
    "Write in English, ONE continuous narration. Return ONLY the text, no commentary, no quotes."
)


def build_default_guide_prompt(
    material: str, facts: str, target_chars: tuple[int, int]
):
    lo, hi = target_chars
    user = (
        f"Target length: ~{lo}-{hi} Chinese-character equivalent (a target, not a hard limit; "
        f"shorter is fine if material is thin).\n\n"
        f"Key facts:\n{facts}\n\nMaterial:\n{material}"
    )
    return _DEFAULT_GUIDE_SYSTEM, user


_MUSEUM_INTRO_SYSTEM = (
    "You write an engaging introduction (~150-220 words total) to a museum for an "
    "audio-guide app, in a warm spoken hook tone, as 2-3 SHORT paragraphs — e.g. "
    "① history/building ② collection highlights & style ③ a one-line invitation — "
    "so it reads comfortably on a phone screen, not as one dense block. Grounded "
    "STRICTLY in the provided MATERIAL — never invent facts; weave stable facts "
    "(founding year, building, collection era) into the narrative. Do NOT mention "
    "opening hours, ticket prices, or visitor logistics. Original wording — do not "
    "copy sentences from the source. Return STRICT JSON: "
    '{"paragraphs": ["paragraph 1 text", "paragraph 2 text", ...]}, no markdown, '
    "no extra keys."
)


def build_museum_intro_prompt(name_en: str, material: str):
    return _MUSEUM_INTRO_SYSTEM, f"Museum: {name_en}\n\nMATERIAL:\n{material}"


_COVER_SAFETY_SYSTEM = (
    "You judge whether an artwork is appropriate as the PUBLIC COVER image / store "
    "listing thumbnail of a museum app (must clear a family-friendly app-store content "
    "rating). Be CONSERVATIVE — this is the storefront, not the in-app content. "
    "Reject ANY work whose subject is a prominent/central nude or sexual content, "
    "EVEN IF it is a canonical artistic masterpiece (e.g. Manet's Olympia, Le Déjeuner "
    "sur l'herbe, Courbet's L'Origine du monde, Cabanel's Birth of Venus). Prefer "
    "unambiguous safe subjects: landscapes, clothed figures, portraits, still life, "
    "architecture, everyday scenes. Reply STRICT JSON: "
    '{"appropriate": true} or {"appropriate": false}.'
)


def build_cover_safety_prompt(title: str, artist, category):
    return (
        _COVER_SAFETY_SYSTEM,
        f"Title: {title}\nArtist: {artist or '?'}\nCategory: {category or '?'}",
    )
