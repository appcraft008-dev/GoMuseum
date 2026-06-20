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
