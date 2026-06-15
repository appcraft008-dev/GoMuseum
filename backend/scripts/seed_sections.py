"""种子：讲解 tab 词表 + 绘画类的 tab 集合（幂等 upsert）。"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.core.database import SessionLocal
from app.models.content import CategorySection, SectionType

SECTION_TYPES = [
    ("overview", "通用描述", "Overview", 10),
    ("artist", "作者介绍", "The Artist", 20),
    ("background", "创作背景", "Background", 30),
    ("analysis", "艺术分析", "Analysis", 40),
    ("significance", "文化意义", "Significance", 50),
    ("facts", "趣闻轶事", "Facts", 60),
]
PAINTING_SECTIONS = [
    "overview",
    "artist",
    "background",
    "analysis",
    "significance",
    "facts",
]


def seed():
    db = SessionLocal()
    try:
        for code, zh, en, sort in SECTION_TYPES:
            st = db.get(SectionType, code) or SectionType(code=code)
            st.label_zh, st.label_en, st.default_sort = zh, en, sort
            db.merge(st)
        db.flush()  # ensure section_types are visible for FK check
        for i, code in enumerate(PAINTING_SECTIONS):
            db.merge(
                CategorySection(
                    category="painting", section_code=code, sort_order=(i + 1) * 10
                )
            )
        db.commit()
        print(
            f"✓ seeded {len(SECTION_TYPES)} section_types, painting -> {len(PAINTING_SECTIONS)} sections"
        )
    finally:
        db.close()


if __name__ == "__main__":
    seed()
