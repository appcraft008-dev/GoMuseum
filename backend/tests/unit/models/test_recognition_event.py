"""recognition_events 模型:字段往返 + 同 phash 允许多行(无唯一约束)。"""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base
from app.models.recognition_event import RecognitionEvent


@pytest.fixture()
def session():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(bind=engine, tables=[RecognitionEvent.__table__])
    return sessionmaker(bind=engine)()


def test_event_roundtrip(session):
    session.add(
        RecognitionEvent(
            museum_slug="orsay",
            phash="abcd",
            outcome="match",
            top_qid="Q1",
            top_score=0.95,
            language="zh",
            engine="vector",
        )
    )
    session.commit()
    row = session.query(RecognitionEvent).one()
    assert row.museum_slug == "orsay"
    assert row.phash == "abcd"
    assert row.outcome == "match"
    assert row.top_qid == "Q1"
    assert row.top_score == 0.95
    assert row.engine == "vector"
    assert row.confirmed_qid is None
    assert row.created_at is not None


def test_same_phash_multiple_rows(session):
    for _ in range(2):
        session.add(
            RecognitionEvent(phash="dup", outcome="unrecognized", engine="text")
        )
    session.commit()
    assert session.query(RecognitionEvent).filter_by(phash="dup").count() == 2


def test_nullable_museum_slug(session):
    session.add(RecognitionEvent(phash="x", outcome="match", engine="cache"))
    session.commit()
    assert session.query(RecognitionEvent).one().museum_slug is None
