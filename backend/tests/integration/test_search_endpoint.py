"""搜索端点契约:全局(museums+objects 两段)vs 馆域(仅 objects)、language、404、空态。"""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.v1.endpoints import search
from app.core.database import Base, get_db
from app.models.artist import Artist
from app.models.museum import Museum
from app.models.museum_object import MuseumObject, ObjectImage
from app.services.object_importer import upsert_museum, upsert_object
from app.services.search import inprocess


@pytest.fixture()
def client():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(
        bind=engine,
        tables=[
            Museum.__table__,
            MuseumObject.__table__,
            ObjectImage.__table__,
            Artist.__table__,
        ],
    )
    TestingSession = sessionmaker(bind=engine)
    s = TestingSession()
    m = upsert_museum(
        s,
        {
            "slug": "orsay",
            "name_zh": "奥赛博物馆",
            "name_en": "Orsay",
            "city_zh": "巴黎",
        },
    )
    upsert_object(
        s,
        m.id,
        {
            "qid": "Q45585",
            "title_en": "The Starry Night",
            "artist_en": "Vincent van Gogh",
            "category": "painting",
            "year": "1889",
            "popularity": 100,
            "image": "http://i/starry.jpg",
            "attributes": {"title_i18n": {"zh": "星夜"}},
        },
    )
    s.commit()
    s.close()
    inprocess._index_cache.clear()

    app = FastAPI()
    app.include_router(search.router)
    app.dependency_overrides[get_db] = lambda: TestingSession()
    yield TestClient(app)
    inprocess._index_cache.clear()


def test_global_search_shape(client):
    body = client.get("/search", params={"q": "星夜"}).json()
    assert body["query"] == "星夜"
    assert "museums" in body and body["objects"][0]["qid"] == "Q45585"
    assert body["objects"][0]["has_image"] is True


def test_global_search_finds_museum(client):
    body = client.get("/search", params={"q": "奥赛"}).json()
    assert any(mu["slug"] == "orsay" for mu in body["museums"])


def test_scoped_search_has_no_museums_segment(client):
    body = client.get("/museums/orsay/search", params={"q": "星夜"}).json()
    assert "museums" not in body
    assert body["objects"][0]["qid"] == "Q45585"


def test_scoped_search_language_en(client):
    body = client.get(
        "/museums/orsay/search", params={"q": "starry", "language": "en"}
    ).json()
    assert body["objects"][0]["title"] == "The Starry Night"


def test_scoped_search_unknown_museum_404(client):
    assert client.get("/museums/nope/search", params={"q": "x"}).status_code == 404


def test_empty_query_returns_empty(client):
    body = client.get("/search", params={"q": ""}).json()
    assert body["objects"] == [] and body["museums"] == []
