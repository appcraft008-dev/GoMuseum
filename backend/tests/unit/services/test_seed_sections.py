import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base
from app.models.content import CategorySection, SectionType


@pytest.fixture()
def session():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(
        bind=engine, tables=[SectionType.__table__, CategorySection.__table__]
    )
    yield sessionmaker(bind=engine)()


def test_seed_creates_multi_category_skeleton(session):
    from scripts.seed_sections import seed_into

    seed_into(session)
    cats = {c.category for c in session.query(CategorySection).all()}
    assert {
        "painting",
        "sculpture",
        "photography",
        "decorative_arts",
        "works_on_paper",
    } <= cats
    painting = [
        c.section_code
        for c in session.query(CategorySection).filter_by(category="painting").all()
    ]
    assert len(painting) == 4 and "artist" not in painting  # artist 成一等实体
    codes = {s.code for s in session.query(SectionType).all()}
    assert {"material-technique", "photographer"} <= codes


def test_seed_covers_the_fallback_categories_too(session):
    """走 _FALLBACK_SECTIONS 的类别也必须拿到 tab 配置。

    这条守的是一个**零报错的隐身 bug**:生成侧用 sections_for()(带兜底),
    而 seed 此前遍历 SECTIONS_BY_CATEGORY.items()(无兜底),于是
    unknown/artifact/manuscript/textile 生成了内容却配置为零行。
    prod 实测 980 段已发布、已过闸、已付费的正文因此在 App 上完全不存在
    (unknown 630 / artifact 330 / manuscript 20,涉及 2826 件)。
    生成报告显示成功、库里内容齐全,只有用户那一侧是空的。
    """
    from app.services.enrichment.category_config import (
        SECTIONS_BY_CATEGORY,
        sections_for,
    )
    from scripts.seed_sections import all_categories, seed_into

    seed_into(session)
    cats = {c.category for c in session.query(CategorySection).all()}
    fallback_cats = all_categories() - set(SECTIONS_BY_CATEGORY)
    assert fallback_cats, "没有走兜底的类别了?那这条测试要重写,别直接删"
    missing = fallback_cats - cats
    assert not missing, f"这些走兜底的类别没拿到 tab 配置: {missing}"
    # 且配的正是兜底那几段、顺序也对（tab 顺序是语义，所以按 sort_order 比）
    for cat in sorted(fallback_cats):
        got = [
            c.section_code
            for c in session.query(CategorySection)
            .filter_by(category=cat)
            .order_by(CategorySection.sort_order)
            .all()
        ]
        assert got == sections_for(cat), f"{cat} 配的段不对: {got}"


def test_seed_registers_every_fallback_code_as_a_section_type(session):
    """兜底段的 code 必须进 section_types —— 否则 category_sections 与
    section_types 的 join 接不上,配了也出不来 tab(等于没修)。
    """
    from app.services.enrichment.category_config import sections_for
    from scripts.seed_sections import all_categories, seed_into

    seed_into(session)
    codes = {s.code for s in session.query(SectionType).all()}
    needed = {c for cat in all_categories() for c in sections_for(cat)}
    assert needed <= codes, f"缺 section_type: {needed - codes}"


def test_seed_registers_guide_section_type_but_not_as_tab(session):
    from scripts.seed_sections import seed_into

    seed_into(session)
    codes = {s.code for s in session.query(SectionType).all()}
    assert "guide" in codes  # 满足 object_content_sections 外键
    guide_tabs = session.query(CategorySection).filter_by(section_code="guide").all()
    assert guide_tabs == []  # guide 不是 6 模块之一，不进任何类目 tab


def test_seed_idempotent(session):
    from scripts.seed_sections import seed_into

    seed_into(session)
    seed_into(session)  # 二次不报错、不重复
    painting = session.query(CategorySection).filter_by(category="painting").all()
    assert len(painting) == 4  # artist 退出 per-work
