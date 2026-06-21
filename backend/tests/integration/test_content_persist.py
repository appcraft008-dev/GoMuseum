# tests/integration/test_content_persist.py
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base
from app.models.content import ObjectContentSection
from app.models.museum import Museum
from app.models.museum_object import MuseumObject, ObjectImage
from app.services.content_repo import persist_explanation
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
    upsert_object(
        s,
        m.id,
        {"qid": "Q1", "title_en": "A", "image": "http://x/a.jpg", "attributes": {}},
    )
    s.commit()
    yield s


def test_persist_explanation(session):
    payload = {
        "summary": "s",
        "historical_context": "h",
        "artistic_analysis": "a",
        "cultural_significance": "c",
        "interesting_facts": ["f1", "f2"],
    }
    assert (
        persist_explanation(session, "Q1", "en", payload, model="gpt-4o-mini") is True
    )
    rows = session.query(ObjectContentSection).all()
    codes = {r.section_code for r in rows}
    assert codes == {"overview", "background", "analysis", "significance", "facts"}
    assert persist_explanation(session, "Q404", "en", payload) is False  # 无此展品


def test_persist_explanation_clears_audio_on_body_change(session):
    payload = {"summary": "s1", "interesting_facts": []}
    persist_explanation(session, "Q1", "en", payload)
    row = (
        session.query(ObjectContentSection)
        .filter_by(language="en", section_code="overview")
        .one()
    )
    row.audio_key = "object-audio/Q1/en/overview.mp3"
    session.commit()

    persist_explanation(session, "Q1", "en", {"summary": "s2", "interesting_facts": []})
    session.refresh(row)
    assert row.body == "s2"
    assert row.audio_key is None


def test_persist_explanation_keeps_audio_on_same_body(session):
    payload = {"summary": "same", "interesting_facts": []}
    persist_explanation(session, "Q1", "en", payload)
    row = (
        session.query(ObjectContentSection)
        .filter_by(language="en", section_code="overview")
        .one()
    )
    row.audio_key = "object-audio/Q1/en/overview.mp3"
    session.commit()

    persist_explanation(session, "Q1", "en", payload)
    session.refresh(row)
    assert row.audio_key == "object-audio/Q1/en/overview.mp3"


def test_persist_generated_sections_upsert(session):
    from app.services.content_repo import persist_generated_sections

    n = persist_generated_sections(
        session,
        "Q1",
        "en",
        {"overview": "An overview.", "artist": None},  # artist None → 不建行
        model="gpt-4o-mini",
    )
    assert n == 1  # 只发布有内容的 overview
    rows = {
        r.section_code: r
        for r in session.query(ObjectContentSection).filter_by(language="en").all()
    }
    assert rows["overview"].body == "An overview."
    assert rows["overview"].status == "published"
    assert rows["overview"].model == "gpt-4o-mini"
    assert rows["overview"].source == "ai_generated"
    assert "artist" not in rows  # 空段不建行


def test_persist_generated_unknown_qid_returns_zero(session):
    from app.services.content_repo import persist_generated_sections

    assert (
        persist_generated_sections(session, "Q404", "en", {"overview": "x"}, model="m")
        == 0
    )
