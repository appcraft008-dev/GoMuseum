"""种子：讲解 tab 词表 + 各类别 tab 集合（幂等 upsert，读 category_config 单一真相源）。"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.core.database import SessionLocal  # noqa: E402
from app.models.content import CategorySection, SectionType  # noqa: E402
from app.services.enrichment.category_config import (  # noqa: E402
    SECTION_LABELS,
    SECTION_SORT,
    SECTIONS_BY_CATEGORY,
    section_label,
)


def seed_into(db) -> None:
    all_codes = {c for codes in SECTIONS_BY_CATEGORY.values() for c in codes}
    for code in all_codes:
        st = db.get(SectionType, code) or SectionType(code=code)
        st.label_zh = section_label(code, "zh")
        st.label_en = section_label(code, "en")
        st.default_sort = SECTION_SORT.get(code, 99)
        db.merge(st)
    db.flush()
    for category, codes in SECTIONS_BY_CATEGORY.items():
        for i, code in enumerate(codes):
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
            f"{len(SECTIONS_BY_CATEGORY)} categories"
        )
    finally:
        db.close()


if __name__ == "__main__":
    seed()
