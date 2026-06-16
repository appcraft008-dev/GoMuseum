import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.api.v1.endpoints.content as content_ep
from app.core.database import Base
from app.main import app
from app.models.content import ObjectContentSection
from app.models.museum import Museum
from app.models.museum_object import MuseumObject, ObjectImage
from app.services.object_importer import upsert_museum, upsert_object
from app.services.tts_service import get_tts_service


class FakeStorage:
    def __init__(self):
        self.objects = {}

    def put(self, key, data, content_type):
        self.objects[key] = data

    def exists(self, key):
        return key in self.objects

    def public_url(self, key):
        return f"https://cdn.test/{key}"


class FakeTTS:
    def __init__(self):
        self.calls = 0

    async def generate_audio(self, text, language="en", voice=None, speed=1.0):
        self.calls += 1
        return {
            "audio_data": b"MP3BYTES",
            "content_type": "audio/mpeg",
            "duration_estimate": 1.0,
            "voice": "x",
            "language": language,
            "text_hash": "h",
            "size_bytes": 8,
        }


@pytest.fixture()
def ctx(monkeypatch):
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
    Session = sessionmaker(bind=engine)
    s = Session()
    m = upsert_museum(s, {"slug": "orsay", "name_en": "Orsay"})
    upsert_object(
        s,
        m.id,
        {"qid": "Q1", "title_en": "A", "image": "http://x/a.jpg", "attributes": {}},
    )
    s.commit()
    s.close()

    storage = FakeStorage()
    fake_tts = FakeTTS()
    # 端点 section 模式用 SessionLocal()（非 Depends(get_db)），故替身工厂
    monkeypatch.setattr(content_ep, "SessionLocal", Session)
    monkeypatch.setattr(content_ep, "get_object_storage", lambda: storage)
    app.dependency_overrides[get_tts_service] = lambda: fake_tts
    client = TestClient(app)
    yield client, fake_tts, storage
    app.dependency_overrides.clear()


SECTION_BODY = {
    "text": "hello",
    "language": "en",
    "qid": "Q1",
    "section_code": "overview",
}


def test_section_mode_generates_and_persists(ctx):
    client, fake_tts, storage = ctx
    r = client.post("/api/v1/content/tts/generate", json=SECTION_BODY)
    assert r.status_code == 200
    body = r.json()
    assert body["cached"] is False
    assert body["audio_url"] == "https://cdn.test/object-audio/Q1/en/overview.mp3"
    assert storage.exists("object-audio/Q1/en/overview.mp3")
    assert fake_tts.calls == 1


def test_section_mode_reuses_without_tts(ctx):
    client, fake_tts, storage = ctx
    client.post("/api/v1/content/tts/generate", json=SECTION_BODY)
    r2 = client.post("/api/v1/content/tts/generate", json=SECTION_BODY)
    assert r2.status_code == 200
    assert r2.json()["cached"] is True
    assert fake_tts.calls == 1


def test_section_mode_unknown_qid_returns_404(ctx):
    client, fake_tts, storage = ctx
    r = client.post(
        "/api/v1/content/tts/generate",
        json={"text": "x", "language": "en", "qid": "Q404", "section_code": "overview"},
    )
    assert r.status_code == 404


def test_ad_hoc_mode_streams_audio(ctx):
    client, fake_tts, storage = ctx
    r = client.post(
        "/api/v1/content/tts/generate", json={"text": "hi", "language": "en"}
    )
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("audio/")
    assert r.content == b"MP3BYTES"
