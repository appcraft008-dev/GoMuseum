import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base
from app.models.content import ObjectContentSection, ObjectSuggestedQuestion
from app.models.museum import Museum
from app.models.museum_object import MuseumObject, ObjectImage
from app.services.object_importer import upsert_museum, upsert_object


@pytest.fixture()
def session():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(
        bind=engine,
        tables=[
            Museum.__table__,
            MuseumObject.__table__,
            ObjectImage.__table__,
            ObjectContentSection.__table__,
            ObjectSuggestedQuestion.__table__,
        ],
    )
    s = sessionmaker(bind=engine)()
    m = upsert_museum(s, {"slug": "orsay", "name_en": "Orsay"})
    upsert_object(s, m.id, {"qid": "Q1", "title_en": "A", "category": "painting"})
    s.commit()
    yield s


def test_suggested_question_roundtrip(session):
    o = session.query(MuseumObject).filter_by(qid="Q1").one()
    row = ObjectSuggestedQuestion(
        object_id=o.id,
        language="en",
        sort=0,
        question="Why the direct gaze?",
        answer="Because ...",
        status="published",
    )
    session.add(row)
    session.commit()
    got = session.query(ObjectSuggestedQuestion).filter_by(object_id=o.id).one()
    assert got.question == "Why the direct gaze?"
    assert got.answer == "Because ..."
    assert got.language == "en" and got.sort == 0
    assert got.status == "published"


def test_persist_suggested_questions_replaces_group(session):
    from app.services.content_repo import persist_suggested_questions

    n = persist_suggested_questions(
        session,
        "Q1",
        "en",
        [
            {"question": "Q-a", "answer": "A-a"},
            {"question": "Q-b", "answer": "A-b", "status": "needs_review"},
        ],
        model="gpt-4o-mini",
    )
    assert n == 1  # 仅 published 计数
    rows = (
        session.query(ObjectSuggestedQuestion)
        .filter_by(language="en")
        .order_by(ObjectSuggestedQuestion.sort)
        .all()
    )
    assert [r.sort for r in rows] == [0, 1]
    assert rows[0].question == "Q-a" and rows[0].status == "published"
    assert rows[1].status == "needs_review"
    assert rows[0].model == "gpt-4o-mini"

    persist_suggested_questions(
        session, "Q1", "en", [{"question": "Q-x", "answer": "A-x"}]
    )
    rows2 = session.query(ObjectSuggestedQuestion).filter_by(language="en").all()
    assert len(rows2) == 1 and rows2[0].question == "Q-x"


def test_persist_suggested_questions_unknown_qid(session):
    from app.services.content_repo import persist_suggested_questions

    assert (
        persist_suggested_questions(
            session, "Q404", "en", [{"question": "a", "answer": "b"}]
        )
        == 0
    )
