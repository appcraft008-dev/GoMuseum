"""种子：讲解 tab 词表 + 各类别 tab 集合（幂等 upsert，读 category_config 单一真相源）。

⚠️ 2026-09-13 修:此前这里遍历的是 `SECTIONS_BY_CATEGORY.items()`,而生成侧用的是
`sections_for(category)` —— 后者带 `_FALLBACK_SECTIONS` 兜底,前者没有。于是
**走兜底的类别(unknown/artifact/manuscript/textile)生成了内容却拿不到 tab 配置**:
prod 实测 980 段已发布、已过闸、已付费的正文因为 category_sections 零行而在 App 上
完全不存在(unknown 630 段 / artifact 330 / manuscript 20,涉及 2826 件)。
全程零报错:生成报告显示成功、库里内容齐全,只有用户那一侧是空的。

修法不是手工给那 4 个类补配置(下次加类别还会掉同一个坑),而是**两侧共用
sections_for()** 并遍历类别全集 —— 以后忘了配 SECTIONS_BY_CATEGORY,
它也会自动拿到兜底 tab,而不是静默消失。
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.core.database import SessionLocal  # noqa: E402
from app.models.content import CategorySection, SectionType  # noqa: E402
from app.services.enrichment.category_config import (  # noqa: E402
    CATEGORY_BY_QID,
    DEFAULT_CATEGORY,
    SECTION_LABELS,
    SECTION_SORT,
    section_label,
    sections_for,
)

# 默认讲解 guide：进 section_types 满足 object_content_sections 外键，但不进任何类目 tab。
_STANDALONE_CODES = {"guide"}


def all_categories() -> set:
    """会真正出现在 museum_objects.category 里的类别全集。

    = P31 映射表的值 + 兜底类别。别只取 SECTIONS_BY_CATEGORY 的键 ——
    那恰好漏掉走兜底的那几类,也就是本文件开头说的那个 bug。
    """
    return set(CATEGORY_BY_QID.values()) | {DEFAULT_CATEGORY}


def seed_into(db) -> None:
    cats = all_categories()
    # 段码全集也要按 sections_for 算:兜底段的 code 必须进 section_types,
    # 否则 category_sections 的外键 join 不上,配了也出不来 tab。
    all_codes = {c for cat in cats for c in sections_for(cat)} | _STANDALONE_CODES
    for code in all_codes:
        st = db.get(SectionType, code) or SectionType(code=code)
        st.label_zh = section_label(code, "zh")
        st.label_en = section_label(code, "en")
        st.default_sort = SECTION_SORT.get(code, 99)
        db.merge(st)
    db.flush()
    for category in sorted(cats):
        for i, code in enumerate(sections_for(category)):
            db.merge(
                CategorySection(
                    category=category, section_code=code, sort_order=(i + 1) * 10
                )
            )
    db.commit()


def seed() -> None:
    db = SessionLocal()
    try:
        seed_into(db)
        print(
            f"✓ seeded {len(SECTION_LABELS)} section_types, "
            f"{len(all_categories())} categories"
        )
    finally:
        db.close()


if __name__ == "__main__":
    seed()
