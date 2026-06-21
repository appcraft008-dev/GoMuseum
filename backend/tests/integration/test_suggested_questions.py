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
