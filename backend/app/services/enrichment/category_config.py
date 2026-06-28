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
        "overview",
        "artist",
        "background",
        "analysis",
        "significance",
        "facts",
    ],
    "sculpture": [
        "overview",
        "artist",
        "material-technique",
        "background",
        "significance",
        "facts",
    ],
    "photograph": ["overview", "photographer", "context", "significance", "facts"],
    "decorative": [
        "overview",
        "maker",
        "material-technique",
        "use",
        "significance",
        "facts",
    ],
}
_FALLBACK_SECTIONS = ["overview", "background", "significance", "facts"]

# 段落 code → 各语言标签（i18n 配置；缺语言回退 en）。
SECTION_LABELS: dict[str, dict[str, str]] = {
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
        "role": "A person with a story: one memorable thing about the maker tied to THIS work, not a CV.",
        "max_chars": 180,
    },
    "background": {
        "role": "The story: commission, scandal, the moment it was made — narrative with momentum.",
        "max_chars": 280,
    },
    "analysis": {
        "role": "Guided looking: 'notice the...', composition, technique, what to SEE. Sensory direction and gentle impressions belong here.",
        "max_chars": 280,
    },
    "significance": {
        "role": "The one takeaway: why it matters / what to remember. The memory point.",
        "max_chars": 140,
    },
    "facts": {
        "role": "One memorable anecdote or curiosity (hard facts live elsewhere).",
        "max_chars": 160,
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
