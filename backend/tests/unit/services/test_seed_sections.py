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
    assert len(painting) == 6 and "artist" in painting
    codes = {s.code for s in session.query(SectionType).all()}
    assert {"overview", "material-technique", "photographer"} <= codes


def test_seed_idempotent(session):
    from scripts.seed_sections import seed_into

    seed_into(session)
    seed_into(session)  # 二次不报错、不重复
    painting = session.query(CategorySection).filter_by(category="painting").all()
    assert len(painting) == 6
