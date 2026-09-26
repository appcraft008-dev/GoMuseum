"""grounded 生成 prompt：只依据材料、类别感知、原创表达、缺料留空。"""

from __future__ import annotations

# 套话黑名单。**单一真相源**:两个 prompt(深度段 _SYSTEM、头条 _DEFAULT_GUIDE_SYSTEM)
# 都用它生成禁令文本,scripts/text_quality_report.py 用同一份统计命中率。
# 分开写两份的下场见过一次(category_sections:生成侧有兜底、展示侧没有,
# 980 段内容因此在 App 上隐身)。这里不重犯:加一条就三处同时生效。
# 清单里每一条都来自**实测**(见下方各 prompt 注释里的命中率),不是凭感觉禁的。
BANNED_PHRASES = [
    "take a moment to",
    "these details matter because",
    "as you stand here",
    "this isn't just a",
    "the composition is carefully structured",
    "interplay of light and shadow",
    # guide 第一轮 A/B 暴露的"二代套话":禁掉开头之后,模型把同样的引导语
    # 挪到了正文中间(实测 "as you take in this" 20 件里命中 13 件)。
    "as you take in",
    "as you gaze",
    "let your gaze",
    "notice how",
]

_BANNED_BLOCK = (
    "BANNED PHRASES (overused to the point of being filler — do not use these or close "
    "variants): " + "; ".join(f"'{p}'" for p in BANNED_PHRASES) + ". "
)

# ⚠️ 2026-09-13:这段 prompt **自己举的例句被模型当模板照抄**。原文在"允许写什么"
# 里举了 'notice the red in the corner' 和 'the brushwork feels restless' 两个例子,
# prod 实测(卢浮宫+奥赛,英语已发布):
#     analysis           477 段: "notice how" 363 (76%)、"brushwork feels" 64 (13%,
#                                其中 6 段连 "feels restless" 都一字未改)
#     material-technique  76 段: "notice how" 35 (46%)
#     background/facts/significance: **全为 0** —— 它们不讲技法,用不到这条例子
# 套话命中率:analysis 94%、material-technique 74%,而 background/facts 0%。
# 规律是「prompt 里要求(或示范)引导观看的段 → 套话;要求陈述事实的段 → 干净」。
# 而**接地闸对此结构性免疫**:它的规则明写"FRAMING/GUIDANCE → KEEP",
# 套话不作事实主张,所以永远过闸 —— 过闸率一路绿灯,没人发现。
# 教训:**在 prompt 里举措辞级的例子,例子本身就会变成输出模板。**
#   要保留"允许引导语"这条语义(接地闸靠它区分事实句与引导句),
#   但改成讲**类别**而不给可抄的措辞,再配黑名单兜底。
_SYSTEM = (
    "You are writing AUDIO-GUIDE narration for a museum visitor standing in front of the "
    "artwork — spoken, not an encyclopedia entry. Voice: vivid storytelling that makes dry "
    "facts come alive WITHOUT inventing anything (think a great popular-history narrator). "
    "Be colloquial and direct, speak to 'you', write people (artists, patrons) as real "
    "humans with motives, use a hook and gentle suspense, vary the rhythm. Each section has "
    "a ROLE and a target length given below; pick the single most engaging angle the "
    "material supports rather than summarizing everything; give one thing worth remembering.\n"
    "What you MAY write freely (these are NOT facts to be checked): framing and "
    "second-person guidance, rhetorical questions, transitions, and GENTLE subjective "
    "impressions clearly phrased as impression. Those are CATEGORIES of allowed writing, "
    "NOT wording to reuse: name what is actually there in fresh words each time. Do NOT "
    "reach for a stock attention-directing formula, and do NOT open a section by telling "
    "the visitor to look or pause — state the thing itself. " + _BANNED_BLOCK + "\n"
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
    museum: str | None = None,
):
    lang = LANG_NAMES.get(target_lang, target_lang)
    system = _TRANSLATION_SYSTEM.format(lang=lang)
    # ⚠️ 下面三处注入的规范名**必须用 XML 标签包,不能用任何一种引号**。
    # 原先写成 「{title}」 —— 直角引号只是随手打的分隔符,却被当成"引用作品名
    # 该怎么写"学走,给法/西/意/德/波的正文套上中日式标点。2026-09-14 实测 prod
    # 存量 3603 段 + 1118 条问答中招(韩语 67.7%、西语 44.8%、法语 33.0%),
    # 已按各语规范批量替换(fr « » / es·it «» / de „“ / pl „”)。
    # 同件 A/B(5 段 × 6 语):中日式标点 20 → **0**,本地引号 es 2→10、fr 10→12。
    # 这是本文件里**第二次**踩同一个坑(第一次见下面 `English:\n` 那条注释),
    # 同一教训的第三次见契约纪律 35。🔑 prompt 里凡"包着一个值"的符号都是示范。
    # (build_faithfulness_prompt 里的 「」 故意不动:那是判定 prompt,只出 JSON
    #  裁决、不出用户可见正文,而且那段措辞是逐字调稳的,改它是纯风险。)
    if title:
        # 标题真相唯一化:正文引用标题一律用显示名(消除内容翻译自选译名的分叉)
        system += (
            f" IMPORTANT: this artwork's canonical {lang} title is "
            f"<canonical_title>{title}</canonical_title> — whenever the text refers "
            f"to the work by name, use EXACTLY this title, do not invent an "
            f"alternative rendering. Punctuate it with {lang}'s own quotation "
            f"conventions; never copy the tags themselves."
        )
    if artist:
        # 作者译名一致性(标题真相唯一化的姊妹):正文称呼作者一律用作者卡规范名
        # (消除音译分叉,如 Seurat 修拉/秀拉——正文与 artists.name_i18n 统一)
        system += (
            f" IMPORTANT: the artist's canonical {lang} name is "
            f"<canonical_artist>{artist}</canonical_artist> — whenever the text "
            f"refers to the artist by name, use EXACTLY this rendering, do not use "
            f"any alternative transliteration. Never copy the tags themselves."
        )
    if museum:
        # 馆名真相唯一化(标题/作者之外的第三类名字):正文提到本馆一律用配置的
        # 权威译名。可字面直译的馆名(Petit Palais)模型会自选直译("小宫殿"),
        # 与馆列表显示的 name_zh("小皇宫美术馆")分叉。
        system += (
            f" IMPORTANT: this museum's canonical {lang} name is "
            f"<canonical_museum>{museum}</canonical_museum> — whenever the text "
            f"refers to the museum by name, use EXACTLY this name, do not translate "
            f"it literally or invent an alternative. Never copy the tags themselves."
        )
    # ⚠️ 别写成 `English:\n{en_body}` —— 那是「语言名: 内容」的格式示范,
    # 模型会照猫画虎在译文前回贴目标语言名(实测 prod 存量 1088 段带
    # "Polish:"/"Italiano:" 前缀)。system 里的 "Return ONLY the translated text"
    # 拦不住:**格式示范比指令更强**。用 XML 标签包裹,不给它可模仿的标签模式。
    user = f"<source_text>\n{en_body}\n</source_text>"
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


# 这个闸**只判事实一致**,不判翻译完整性 —— 后者由 `lang_detect.text_in_language`
# 独立判(qa_suggester 的 lang_ok / translator 的 _lang_ok),两处调用方都会 and 起来。
# 曾经两件事压在同一个布尔里,实测拦截理由绝大多数是后者、且判得很差:
#   「'Statue of Liberty' 没翻译,留成 'Freiheit erleuchtet die Welt'」——那正是德语规范译名
#   「'which translates to' 没翻译」「'Canal du Loing' 没翻译」(法语地名本就该保留)
#   「'Tiara Sajtafernesa' 是英语没翻译」(那是波兰语)
# 拆开后实测(40 挂起 / 30 已发布 / 15 人为破坏三组对照):挂起组 2%→45% 判通过,
# 已发布组 100%→100% 零误伤,**人为破坏组 0% 通过、零漏网**(闸没被拆坏)。契约纪律 26。
_FAITHFULNESS_SYSTEM = (
    "You are a translation FACT judge. You are given an English SOURCE and its {lang} "
    "TRANSLATION. Judge ONE thing only: does the translation state the same facts as the "
    "source — nothing added, nothing omitted, nothing altered (names, dates, places, "
    "attributions, what is depicted)? Wording, fluency, style and word order differences "
    "are fine.\n"
    "Do NOT judge translation completeness or terminology choice. In particular, a proper "
    "noun, place name, institution or work title left in its original or conventional form "
    "is NOT a fault — never flag it. Whether the text is written in {lang} is checked "
    "elsewhere; ignore it here.\n"
    'Return STRICT JSON: {{"faithful": true|false, "issues": ["..."]}} '
    "(issues empty if faithful). No commentary."
)


def build_faithfulness_prompt(
    en_body: str,
    translated: str,
    target_lang: str,
    title: str | None = None,
    artist: str | None = None,
):
    """[title]/[artist] 该作品与其作者在目标语言的**规范名**
    (来自 title_i18n / artists.name_i18n,源头是 Wikidata 标签)。

    ⚠️ 翻译侧注入了什么规范名,检查侧就必须知道什么 —— 否则它拿英文的直译当标准,
    把正确的传统名判成错译,而强模型重译仍用同一个名字 →
    **重跑一万次也修不好,因为两侧假设冲突**(契约纪律 22)。

    实测两个同构实例:
    - 标题:Q3745385《Red-Haired Girl》德语传统名「Russisches Mädchen」、
      意语 Wikidata 标签「Fille rousse」—— 检查器报 "incorrectly refers to the
      painting as ... instead of 'Rothaariges Mädchen'",de/it 两段永久卡死。
    - 作者:539 段复检里判「真不忠实」的 147 段,抱怨的几乎全是作者名
      (「'Michel-Ange Buronarroti' 应为 'Michel-Ange'」「'Vouet' 不该译成 '西蒙·沃特'」)。

    末句的 "ONLY to these name forms" 是**防止整体放宽**的护栏:实测这段 NOTE 不是
    在放水(60 条抽样里约 50 条抱怨的确实是标题),但加入作者名后覆盖面更宽,
    必须显式圈定它只豁免名字写法,其余照常判。

    ⚠️ 2026-09-03 复测:上面这版 NOTE **仍会被判定模型无视**——原样复现
    Q3745385/de(「Russisches Mädchen」),issues 报 "'Red-Haired Girl' should be
    'Russisches Mädchen'"(mini 判/gpt-4o 判定通道各判 3 次,结果完全一致,非随机)。
    NOTE 的问题是"陈述规则"而非"给出指令"——模型仍把名字差异当证据去推理。
    改成 STEP0/STEP1 两步式:先明确要求"删除/忽略这两个字符串再判"、配一个
    与本作品无关的示例(The Hague/Den Haag,字母全不沾边但正确)让模型认出这
    一类模式,才稳定判 faithful(mini 3/3 True;换成逐字对应本案例的示例效果一样,
    但通用示例不用多传英文原名参数,更省)。人为破坏对照组(改年份+加事实)
    3/3 正确拒绝,只传 artist 不传 title 的路径也验过、不崩、照样正确拒绝——
    闸没被拆松。契约纪律 26 的方法论在此复用。
    """
    lang = LANG_NAMES.get(target_lang, target_lang)
    system = _FAITHFULNESS_SYSTEM.format(lang=lang)
    names = []
    if title:
        names.append(f"title -> 「{title}」")
    if artist:
        names.append(f"artist -> 「{artist}」")
    note = ""
    if names:
        mapping = "; ".join(names)
        note = (
            f"STEP 0 (do this first, silently): the translation is REQUIRED to render "
            f"these using their canonical {lang} forms, NOT a literal translation of the "
            f"English: {mapping}. Delete/ignore every occurrence of these strings in the "
            f"TRANSLATION before you judge anything else — they are pre-approved and "
            f"structurally CANNOT be an infidelity, no matter how different they look from "
            f"the English (many artwork titles and artist names are conventionally quite "
            f"different across languages, e.g. an English 'The Hague' is 'Den Haag' in "
            f"Dutch with no shared letters, and that mismatch is CORRECT, not an error). "
            f"Do not reason about them, do not mention them, do not include any issue "
            f"whose subject is a name/title translation choice.\n"
            f"STEP 1: now judge only the remaining facts (dates, places, what is depicted, "
            f"attributions, events) for the usual add/omit/alter faithfulness check.\n\n"
        )
    user = f"{note}SOURCE (English):\n{en_body}\n\nTRANSLATION ({lang}):\n{translated}"
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


# ⚠️ 这段 prompt 里**一个套话也没写**,模型却自己把 5 beats 的骨架每次填成
# 同一套措辞。2026-09-13 实测 prod(英语 guide,284 件样本):
#     "take a moment to really"        248 件 (87.3%)
#     "as you stand here think about"  156 件 (54.9%)
#     "these details matter because"    98 件 (34.5%)
#   → 282 段只有 38 种开头(多样性 13%),而 background/significance/facts
#     的开头多样性是 96-99%,所以这是 guide 这段**独有**的病。
# 结构化指令 + 低温度会让措辞收敛:骨架越明确,模型越倾向用固定过渡语填它。
# 而**接地闸对此结构性免疫** —— 闸的规则写着"引导句无可证伪事实 → keep=True",
# 套话不陈述事实,所以永远过闸,过闸率一路绿灯,25635 段里没人发现。
# 所以这里同时下三道:正面要求(开场必须携带本件独有的具体物)、
# 负面清单(实测高频句)、元要求(别把一种套话换成另一种)。
# 改动后用 scripts/text_quality_report.py 复测,别靠看几段样本拍脑袋。
#
# A/B 实测(三馆 top20、同材料同模型 gpt-4o-mini/0.3、只换 system,
# 并以**旧 prompt 现场重生成**为对照组 —— 没有对照就分不清"prompt 起作用"
# 和"这次抽样刚好不同";卢浮宫跑了三轮,对照组三轮都与线上现状逐项吻合):
#                  开头多样性(旧→新)  锚点率(旧→新)  二代套话残留  接地存活率(旧→新)
#     卢浮宫          40% → 95%        43% → 63%        25%       .932 → .952
#     奥赛            30% → 90%        42% → 54%        50%       .990 → .963
#     小皇宫(stub)    25% → 100%       47% → 58%        40%       .943 → .937
# ⚠️ 关键护栏:三馆过闸率全是 20/20。**锚点率上升不是靠编年份**,是让模型
#     去材料里找本来就有的具体事实。没有这条护栏,"锚点率提升"可能恰恰是
#     质量倒退(为满足"开场要有年份"而编造)。
# ⚠️ 已知残留:禁掉开头之后仍有 25-50% 的段用某句引导语(当前是
#     "as you take in this")。继续加禁用词收益递减且会把文本写僵,故停手;
#     指标已进仓库,可持续监控而不是又变回看不见。
# ⚠️ **残留量与材料厚度没看出关系** —— 这条是撤回的一个错推论,留着免得有人
#   再走一遍:先只有卢浮宫(残留 25%)和奥赛(50%)两个点时,曾以为"材料越薄
#   残留越多",还据此预测小皇宫会最差。小皇宫实测 40%(介于两者之间)、
#   开头多样性 100%(三馆最好),预测被推翻。两个错处:
#     ① 拿 significance **挂起件**的 extract_en 覆盖率当"该馆材料厚度",
#        分母错了。三馆 top20 实测材料中位 21166/18643/16748 字符、
#        维基正文 20/20、20/20、4/4 —— 热门件材料都厚,没有"薄馆"。
#     ② 两个点永远能连成一条线。
#   顺带一个更强的结论:小皇宫那组材料包中位只有 3489 字符(stub 件,
#   没建 evidence_pack),**材料最薄却效果最好** → prompt 的改善不依赖材料厚度。
_DEFAULT_GUIDE_SYSTEM = (
    "You are a museum audio-guide writer. Write ONE short spoken on-site guide for a visitor "
    "standing in front of the artwork, built around a SINGLE core point (one throughline) — "
    "not a summary of everything. Structure (5 beats, flowing, not labeled): "
    "(1) a hook that gets them looking; (2) POINT OUT 1-2 concrete details by describing "
    "them directly — name what is there, do not preface it with a phrase that tells the "
    "visitor to look; (3) explain why those details matter — carry the meaning inside the "
    "sentence itself; do NOT open it with 'These details…' / 'This detail…' / 'Such "
    "details…' as the subject; (4) add only the necessary "
    # ⚠️ 2026-09-13 第二轮:#543 之后 guide 仍有 45% 违反**自己 prompt 里的**禁用词
    # (prod 实测 20 段中 9 段:8 段 `as you take in`、1 段 `as you stand here`),
    # 而深度段用同一个 _BANNED_BLOCK 是 0 违反。查下来根因不在黑名单:
    #   **违规全部出现在结尾句**,而这一拍原本只有"end on a memory point or an
    #   open question"一句话,完全没说怎么进入结尾 —— 关于**开头**的约束却极具体
    #   (7 条 BANNED OPENINGS + 明确禁止以邀请观看开头)。模型不是在违抗禁令,
    #   是在执行第 5 拍,而它只会一个公式:「As you <动词> this <名词>, consider…」。
    # 先后证伪过三个推论(都做了 A/B,别再走一遍):
    #   ① "#546 去套话改动打崩了它" → 旧/新 prompt 同件 A/B,新的还略好;
    #   ② "第(1)拍'hook that gets them looking'与禁令自相矛盾" → 改掉无效(5/10);
    #   ③ "'MAY freely use framing guidance'把它放出来了" → 收紧无效(5/10)。
    # 只有约束结尾这一拍有效:**6/10 → 0/10**,接地存活 0.98→0.96(没靠少说话换)。
    # 🔑 通法:**笼统的禁用词清单打不过具体的结构指令 —— 禁令要长在指令所在的那一拍上。**
    # ⚠️ 2026-09-26 第三轮:黑名单开头与 As-you 结尾都清掉后,guide 换了三个槽位模板
    # (小皇宫 TOP20):首句「In {年}, {作者} captured a moment…」14/19、第三拍
    # 「These details…」11/19、结尾反问 19/19(「What feelings does this evoke…?」)。
    # 都是**本 prompt 自己的指令**被执行成公式:"open question" 被当默认、"首句必须带
    # 年份/人名" 被当成「年份+人名开头」。所以约束仍写在各自那一拍上,不另起清单。
    # A/B 第一版证伪了「end on a memory point」这个说法本身:问句 20/20→0/20,但模型把
    # "memory point" 执行成「The image of X … lingers in the mind / Remember the image
    # of…」(30 件约 25 件)—— 词本身就是模板种子。所以结尾不再提"记住/画面",改成
    # 「最后一个没讲过的具体事实,说完就停」。开头「禁 In YEAR, ARTIST captured 框架」
    # 只从 15/20 压到 10/20 → 换成可检查的硬约束:首句不放年份。
    # A/B 第二版:「再补一个没讲过的事实收尾」逼模型去凑事实 —— 闸删的句子集中到了
    # **最后一句**(10 句 vs 旧版 3 句),接地均值 0.926→0.888,删完正文停在半截;
    # 没被删的则变成念目录(「measures X by Y cm」「housed in the Petit Palais」)。
    # 开头改成「首句不放年份」后又长出「In 'TITLE,' ARTIST captures…」10/20。
    # 所以:结尾不要求新内容(主线讲完就停),开头不拿标题/作者当句子框架。
    "background; (5) stop when the throughline is complete. There is no separate closing "
    "beat: the last sentence stays on something specific already set up in THIS guide, "
    "and adds no new fact just to have an ending. The last sentence must NOT be a "
    "question to the visitor, a moral, a sentence about what the work 'remains', "
    "'reminds us of', 'embodies' or how it 'lingers', an instruction to remember, or "
    "catalogue data (dimensions, where it is housed, how it was acquired). Do NOT begin "
    "it with 'As you…', 'Next time you…', 'When you…', 'Standing here…', 'Notably…' or "
    "any similar lead-in. "
    "OPENING: the first sentence MUST carry something specific to THIS work — a named "
    "person, a place, a number, or one concrete thing visible in it — so that it could "
    "not be pasted onto any other artwork. Begin with the subject itself (the person, "
    "object or event in the work), NOT with the title, artist or year as the frame of "
    "the sentence ('In YEAR, ARTIST captured…', 'In TITLE, ARTIST presents…', "
    '"ARTIST\'s TITLE captures…" open most guides already, and title, artist and date '
    "are shown on screen above the guide). "
    # ⚠️ 别加「没有看图块就别从外观开头」这类条件句:试过(v4),无看图描述的件照样
    # 编外观(毛绒扶手椅),旧 prompt 在同样的件上也编 —— 这是接地闸对外观描写的
    # 老盲区,不是本条引入的;防线是生成前先看图(pipeline 里的 ensure_description)。
    # 我一度以为是本条引入的,实为误判:留出集 10 件里 5 件本来就有看图描述,
    # 「蓝腰带红披风」「红金铠甲」都出自描述。
    "Do NOT open by inviting the visitor to look or pause. "
    "BANNED OPENINGS (overused to the point of being filler): 'Take a moment…', "
    "'As you look at…', 'As you stand…', 'Stand before…', 'Picture this…', "
    "'Imagine standing…', 'Let's take a closer look…'. "
    + _BANNED_BLOCK
    + "The 5 beats are a SHAPE, not wording: do not use recurring connective formulas to "
    "move between them, and do not swap one banned formula for a new fixed one — vary how "
    "you enter and close from work to work. In particular, do NOT use ANY stock phrase "
    "that directs attention ('observe…', 'look at how…', 'pay attention to…'): the visitor "
    "is already in front of the work, so simply state what is there and what it means. "
    "Voice: colloquial, second-person, vivid storytelling that makes facts come alive "
    "(a great popular-history narrator). You MAY freely use framing/second-person guidance "
    "and gentle impressions clearly phrased as impression. You MUST NOT invent verifiable "
    "facts (names, dates, events, attributions, medium, what is depicted) not in the material. "
    "If the material is too thin for a specific opening, open on the most concrete fact you "
    "DO have (medium, dimensions, where it came from) — never pad with an invitation to look. "
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
    "audio-guide app, in a warm spoken hook tone, split into 3 DISTINCT short "
    "paragraphs so it reads comfortably on a phone screen, not as one dense block. "
    "Grounded STRICTLY in the provided MATERIAL — never invent facts; weave stable "
    "facts (founding year, building, collection era) into the narrative. Do NOT "
    "mention opening hours, ticket prices, or visitor logistics. Original wording — "
    "do not copy sentences from the source. Return STRICT JSON with EXACTLY these "
    "three keys, each a non-empty paragraph string — do NOT merge them into one key: "
    '{"history": "paragraph about history/building", '
    '"highlights": "paragraph about collection highlights and style", '
    '"invitation": "one short inviting closing line"}'
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
