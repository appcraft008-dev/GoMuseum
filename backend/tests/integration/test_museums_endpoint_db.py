# tests/integration/test_museums_endpoint_db.py
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base, get_db
from app.main import app
from app.models.museum import Museum
from app.models.museum_object import MuseumObject, ObjectImage
from app.services.object_importer import upsert_museum, upsert_object


@pytest.fixture()
def client():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(
        bind=engine,
        tables=[Museum.__table__, MuseumObject.__table__, ObjectImage.__table__],
    )
    Session = sessionmaker(bind=engine)
    s = Session()
    m = upsert_museum(
        s,
        {
            "slug": "orsay",
            "name_zh": "奥赛",
            "name_en": "Orsay",
            "city_zh": "巴黎",
            "city_en": "Paris",
            "country": "FR",
            "qid": "Q23402",
        },
    )
    upsert_object(
        s,
        m.id,
        {
            "qid": "Q1",
            "title_zh": "甲",
            "title_en": "A",
            "artist_zh": "X",
            "artist_en": "X",
            "year": "1880",
            "period_zh": "现实主义",
            "period_en": "Realism",
            "popularity": 50,
            "image": "http://x/a.jpg",
            "attributes": {},
        },
    )
    s.commit()
    app.dependency_overrides[get_db] = lambda: (yield s)
    yield TestClient(app)
    app.dependency_overrides.pop(get_db, None)
    s.close()


def test_list_endpoint(client):
    r = client.get("/api/v1/museums")
    assert r.status_code == 200
    assert r.json()[0]["slug"] == "orsay"
    assert r.json()[0]["artwork_count"] == 1


def test_pack_endpoint(client):
    r = client.get("/api/v1/museums/orsay")
    assert r.status_code == 200
    body = r.json()
    assert body["artwork_count"] == 1
    assert body["artworks"][0]["title_en"] == "A"


def test_pack_404(client):
    assert client.get("/api/v1/museums/nope").status_code == 404
