"""类别单一真相源：Wikidata P31 QID → canonical 类别名。
seed/抓取/生成器/prompt 共用，加新类别=改这里、零代码。"""

from __future__ import annotations

CATEGORY_BY_QID: dict[str, str] = {
    "Q3305213": "painting",
    "Q860861": "sculpture",
    "Q125191": "photograph",
}
DEFAULT_CATEGORY = "unknown"


def category_for(p31_qid: str | None) -> str:
    return CATEGORY_BY_QID.get(p31_qid or "", DEFAULT_CATEGORY)


# 类别 → 有序段落集（单一真相源；seed/生成/详情共用）。未知类别用 _FALLBACK。
SECTIONS_BY_CATEGORY: dict[str, list[str]] = {
    "painting": [
        "background",
        "analysis",
        "significance",
        "facts",
    ],
    "sculpture": [
        "material-technique",
        "background",
        "significance",
        "facts",
    ],
    "photograph": ["photographer", "context", "significance", "facts"],
    "decorative": [
        "maker",
        "material-technique",
        "use",
        "significance",
        "facts",
    ],
}
_FALLBACK_SECTIONS = ["background", "significance", "facts"]

# 段落 code → 各语言标签（i18n 配置；缺语言回退 en）。
SECTION_LABELS: dict[str, dict[str, str]] = {
    "guide": {
        "zh": "标准导览",
        "en": "Standard Guide",
        "fr": "Visite guidée",
        "de": "Standardführung",
        "es": "Guía estándar",
        "it": "Guida standard",
    },
    "overview": {
        "zh": "通用描述",
        "en": "Overview",
        "fr": "Aperçu",
        "de": "Überblick",
        "es": "Resumen",
        "it": "Panoramica",
    },
    "artist": {
        "zh": "作者介绍",
        "en": "The Artist",
        "fr": "L'artiste",
        "de": "Der Künstler",
        "es": "El artista",
        "it": "L'artista",
    },
    "photographer": {
        "zh": "摄影师",
        "en": "The Photographer",
        "fr": "Le photographe",
        "de": "Der Fotograf",
        "es": "El fotógrafo",
        "it": "Il fotografo",
    },
    "maker": {
        "zh": "制作者",
        "en": "The Maker",
        "fr": "Le créateur",
        "de": "Der Hersteller",
        "es": "El creador",
        "it": "Il creatore",
    },
    "material-technique": {
        "zh": "材质工艺",
        "en": "Material & Technique",
        "fr": "Matériaux et technique",
        "de": "Material und Technik",
        "es": "Material y técnica",
        "it": "Materiali e tecnica",
    },
    "background": {
        "zh": "创作背景",
        "en": "Background",
        "fr": "Contexte",
        "de": "Hintergrund",
        "es": "Contexto",
        "it": "Contesto",
    },
    "context": {
        "zh": "拍摄背景",
        "en": "Context",
        "fr": "Contexte",
        "de": "Kontext",
        "es": "Contexto",
        "it": "Contesto",
    },
    "use": {
        "zh": "用途",
        "en": "Use",
        "fr": "Usage",
        "de": "Verwendung",
        "es": "Uso",
        "it": "Uso",
    },
    "analysis": {
        "zh": "艺术分析",
        "en": "Analysis",
        "fr": "Analyse",
        "de": "Analyse",
        "es": "Análisis",
        "it": "Analisi",
    },
    "significance": {
        "zh": "文化意义",
        "en": "Significance",
        "fr": "Signification",
        "de": "Bedeutung",
        "es": "Significado",
        "it": "Significato",
    },
    "facts": {
        "zh": "趣闻轶事",
        "en": "Facts",
        "fr": "Anecdotes",
        "de": "Fakten",
        "es": "Datos",
        "it": "Curiosità",
    },
}
SECTION_SORT = {
    "overview": 10,
    "artist": 20,
    "photographer": 20,
    "maker": 20,
    "material-technique": 30,
    "background": 30,
    "context": 30,
    "use": 35,
    "analysis": 40,
    "significance": 50,
    "facts": 60,
}


def sections_for(category: str) -> list[str]:
    return SECTIONS_BY_CATEGORY.get(category, _FALLBACK_SECTIONS)


def section_label(code: str, lang: str) -> str:
    labels = SECTION_LABELS.get(code, {})
    return labels.get(lang) or labels.get("en") or code


# 各段在语音导览里的角色 + 目标长度（中文字数；长度是目标非硬限，料薄可短）。spec §4。
SECTION_ROLES: dict[str, dict] = {
    "overview": {
        "role": "The HOOK: one vivid opening line that makes the visitor look up. Not a dry 'X is a painting by Y'.",
        "max_chars": 100,
    },
    "artist": {
        "role": "The MAKER as a person: life, character, what drove them, their place in art history. NOT this work's scandal/technique (other lanes cover those).",
        "max_chars": 260,
    },
    "background": {
        "role": "The work's HISTORY as concrete events: when, who commissioned it, where shown, the reception as events, provenance. NOT why-it-matters (that's significance), NOT how-to-look (that's analysis).",
        "max_chars": 380,
    },
    "analysis": {
        "role": "HOW it's painted — the craft: brushwork, paint handling, light & colour, composition structure, scale. Explain technique and the choices behind the effect. Do NOT re-list the symbols/subjects the headline guide already pointed out; go beyond naming them to how the painting achieves its impact.",
        "max_chars": 380,
    },
    "significance": {
        "role": "LEGACY & influence: what it changed, who it influenced, why it matters to art history. Do NOT re-tell the scandal events (that's background).",
        "max_chars": 240,
    },
    "facts": {
        "role": "ONE surprising anecdote/curiosity not covered by other lanes.",
        "max_chars": 200,
    },
    "photographer": {
        "role": "A person with a story: one memorable thing about the maker tied to THIS work.",
        "max_chars": 180,
    },
    "maker": {
        "role": "A person with a story: one memorable thing about the maker tied to THIS work.",
        "max_chars": 180,
    },
    "material-technique": {
        "role": "Guided looking at how it was made: material and craft a visitor can notice.",
        "max_chars": 200,
    },
    "context": {
        "role": "The story and moment behind the work — narrative with momentum.",
        "max_chars": 280,
    },
    "use": {
        "role": "What it was for and how it lived — concrete and human.",
        "max_chars": 200,
    },
}

_DEFAULT_ROLE = {
    "role": "Engaging, grounded spoken narration for a museum visitor.",
    "max_chars": 180,
}


def section_role(code: str) -> dict:
    return SECTION_ROLES.get(code, _DEFAULT_ROLE)


# 默认讲解长度档（中文字，已×1.5）。重点件 = popularity>=阈值。spec §3.1。
GUIDE_KEY_THRESHOLD = 30


def guide_target_chars(popularity: int | None) -> tuple[int, int]:
    if (popularity or 0) >= GUIDE_KEY_THRESHOLD:
        return (420, 675)
    return (270, 420)


def section_target_chars(code: str, popularity: int | None) -> int:
    """模块字数上限,按热度分档:重点件(>=阈值)base×1.5,普通件 base。"""
    base = SECTION_ROLES.get(code, _DEFAULT_ROLE)["max_chars"]
    if (popularity or 0) >= GUIDE_KEY_THRESHOLD:
        return int(base * 1.5)
    return base
