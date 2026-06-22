import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base
from app.models.content import ObjectContentSection
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
        ],
    )
    s = sessionmaker(bind=engine)()
    m = upsert_museum(s, {"slug": "orsay", "name_en": "Orsay"})
    upsert_object(s, m.id, {"qid": "Q1", "title_en": "A", "category": "painting"})
    s.commit()
    yield s


def test_content_status_defaults_to_stub(session):
    o = session.query(MuseumObject).filter_by(qid="Q1").one()
    assert o.content_status == "stub"


def test_backfill_sets_ready_for_objects_with_published_sections(session):
    from app.services.enrichment.backfill import backfill_content_status

    o = session.query(MuseumObject).filter_by(qid="Q1").one()
    session.add(
        ObjectContentSection(
            object_id=o.id,
            language="en",
            section_code="overview",
            body="x",
            status="published",
        )
    )
    upsert_object(
        session, o.museum_id, {"qid": "Q2", "title_en": "B", "category": "painting"}
    )
    session.commit()

    counts = backfill_content_status(session)
    assert counts == {"ready": 1, "stub": 1}
    assert (
        session.query(MuseumObject).filter_by(qid="Q1").one().content_status == "ready"
    )
    assert (
        session.query(MuseumObject).filter_by(qid="Q2").one().content_status == "stub"
    )


def test_backfill_idempotent(session):
    from app.services.enrichment.backfill import backfill_content_status

    backfill_content_status(session)
    assert backfill_content_status(session) == {"ready": 0, "stub": 1}
