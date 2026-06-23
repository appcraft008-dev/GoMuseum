import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.v1.endpoints import museums
from app.core.database import Base, get_db
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
    TestingSession = sessionmaker(bind=engine)
    s = TestingSession()
    m = upsert_museum(s, {"slug": "orsay", "name_en": "Orsay"})
    upsert_object(
        s, m.id, {"qid": "Q1", "title_en": "A", "category": "painting", "popularity": 9}
    )
    s.commit()
    s.close()

    app = FastAPI()
    app.include_router(museums.router, prefix="/museums")
    app.dependency_overrides[get_db] = lambda: TestingSession()
    return TestClient(app)


def test_objects_endpoint_returns_page(client):
    r = client.get("/museums/orsay/objects", params={"limit": 10, "offset": 0})
    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 1 and body["limit"] == 10
    assert body["items"][0]["qid"] == "Q1"
    assert "content_status" in body["items"][0]


def test_objects_endpoint_unknown_museum_404(client):
    assert client.get("/museums/nope/objects").status_code == 404
