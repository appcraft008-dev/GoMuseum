import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base
from app.models.content import ObjectContentSection
from app.models.museum import Museum
from app.models.museum_object import MuseumObject, ObjectImage
from app.services.content_repo import persist_section_audio
from app.services.object_importer import upsert_museum, upsert_object


class FakeStorage:
    def __init__(self):
        self.objects = {}

    def put(self, key, data, content_type):
        self.objects[key] = (data, content_type)

    def exists(self, key):
        return key in self.objects

    def public_url(self, key):
        return f"https://cdn.test/{key}"


class BoomStorage(FakeStorage):
    def put(self, key, data, content_type):
        raise RuntimeError("r2 down")


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


def test_persist_section_audio_uploads_and_writes_key(session):
    storage = FakeStorage()
    key = persist_section_audio(session, "Q1", "en", "overview", b"MP3", storage)
    assert key == "object-audio/Q1/en/overview.mp3"
    assert storage.exists(key)
    row = (
        session.query(ObjectContentSection)
        .filter_by(language="en", section_code="overview")
        .one()
    )
    assert row.audio_key == key


def test_persist_section_audio_unknown_qid_returns_none(session):
    storage = FakeStorage()
    assert (
        persist_section_audio(session, "Q404", "en", "overview", b"x", storage) is None
    )
    assert storage.objects == {}


def test_persist_section_audio_upload_failure_writes_no_key(session):
    with pytest.raises(RuntimeError):
        persist_section_audio(session, "Q1", "en", "overview", b"x", BoomStorage())
    row = (
        session.query(ObjectContentSection)
        .filter_by(language="en", section_code="overview")
        .one_or_none()
    )
    assert row is None or row.audio_key is None
