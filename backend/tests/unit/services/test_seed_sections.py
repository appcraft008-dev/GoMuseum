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
    assert {"painting", "sculpture", "photograph", "decorative"} <= cats
    painting = [
        c.section_code
        for c in session.query(CategorySection).filter_by(category="painting").all()
    ]
    assert len(painting) == 4 and "artist" not in painting  # artist 成一等实体
    codes = {s.code for s in session.query(SectionType).all()}
    assert {"material-technique", "photographer"} <= codes


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
