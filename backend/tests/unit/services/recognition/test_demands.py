"""未收录需求记录:同 (馆, phash) 幂等计数聚合。"""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base
from app.models.recognition_demand import RecognitionDemand
from app.services.recognition.demands import record_demand


@pytest.fixture()
def session():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(bind=engine, tables=[RecognitionDemand.__table__])
    s = sessionmaker(bind=engine)()
    yield s


def test_first_record_counts_one(session):
    n = record_demand(session, "orsay", "ph1", label_text="Le Chat blanc")
    assert n == 1
    row = session.query(RecognitionDemand).one()
    assert row.label_text == "Le Chat blanc" and row.hit_count == 1


def test_same_phash_increments_not_duplicates(session):
    record_demand(session, "orsay", "ph1")
    n = record_demand(session, "orsay", "ph1", label_text="补拍到的标签")
    assert n == 2
    rows = session.query(RecognitionDemand).all()
    assert len(rows) == 1
    assert rows[0].label_text == "补拍到的标签"  # 后到的墙签文字更新进去


def test_different_phash_separate_rows(session):
    record_demand(session, "orsay", "ph1")
    record_demand(session, "orsay", "ph2", candidates=[{"title": "X"}])
    assert session.query(RecognitionDemand).count() == 2
