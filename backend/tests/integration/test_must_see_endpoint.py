"""GET /api/v1/museums/{slug}/must-see 与馆列表 must_see_count(spec 2026-10-27 §五.4)。"""

from datetime import datetime
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base, get_db
from app.main import app
from app.models.artist import Artist
from app.models.content import ObjectContentSection
from app.models.museum import Museum
from app.models.museum_object import MuseumObject, ObjectImage
from app.models.must_see_medal import MustSeeMedal
from app.models.recognition_event import RecognitionEvent
from app.services import must_see
from app.services.object_importer import upsert_museum, upsert_object

AUTH = {"Authorization": "Bearer t"}


@pytest.fixture()
def db(monkeypatch):
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
            Artist.__table__,
            RecognitionEvent.__table__,
            MustSeeMedal.__table__,
        ],
    )
    s = sessionmaker(bind=engine)()
    for slug, published in (("orsay", True), ("hidden", False), ("plain", True)):
        m = upsert_museum(s, {"slug": slug, "name_en": slug})
        m.published_at = datetime(2026, 1, 1) if published else None
        if slug == "orsay":
            for q, pop in (("Q1", 1), ("Q2", 99), ("Q3", 50)):
                upsert_object(
                    s,
                    m.id,
                    {
                        "qid": q,
                        "title_en": f"T{q}",
                        "artist_en": "A",
                        "popularity": pop,
                        "image": f"http://x/{q}.jpg",
                        "attributes": {},
                    },
                )
    s.commit()
    # 清单顺序 Q2, Q1, QMISSING(目录里没有)
    monkeypatch.setitem(must_see.MUST_SEE, "orsay", ["Q2", "Q1", "QMISSING"])
    monkeypatch.setitem(must_see.MUST_SEE, "hidden", ["Q1"])
    monkeypatch.setitem(
        must_see.MUST_SEE_LOCATION,
        "orsay",
        {"Q2": {"wing": None, "level": 5, "room": "29"}},
    )
    return s


@pytest.fixture()
def client(db, monkeypatch):
    from app.services.auth_service import AuthService

    user = SimpleNamespace(id="u", is_guest=False, can_preview=False)
    monkeypatch.setattr(
        AuthService, "get_current_user", staticmethod(lambda d, t: user)
    )
    app.dependency_overrides[get_db] = lambda: (yield db)
    yield TestClient(app)
    app.dependency_overrides.pop(get_db, None)


def test_items_in_list_order_with_location_and_fallback(client):
    r = client.get("/api/v1/museums/orsay/must-see?language=en")
    assert r.status_code == 200
    items = r.json()["items"]
    assert [i["qid"] for i in items] == ["Q2", "Q1", "QMISSING"]
    assert items[0]["title"] == "TQ2" and items[0]["artist"] == "A"
    assert items[0]["location"] == {"wing": None, "level": 5, "room": "29"}
    assert items[1]["location"] is None
    assert items[2] == {
        "qid": "QMISSING",
        "title": "QMISSING",
        "artist": "",
        "thumbnail": None,
        "location": None,
    }


def test_anonymous_gets_list_without_progress(client):
    body = client.get("/api/v1/museums/orsay/must-see").json()
    assert body["checked"] == {} and body["medals"] == []
    assert body["completed"] is False and body["round_started_at"] is None


def test_progress_with_token(client, db):
    db.add(
        RecognitionEvent(
            phash="p",
            outcome="match",
            top_qid="Q2",
            engine="vector",
            user_id="u",
            capture="camera",
        )
    )
    db.commit()
    body = client.get("/api/v1/museums/orsay/must-see", headers=AUTH).json()
    assert list(body["checked"]) == ["Q2"]
    assert body["round_started_at"].endswith("+00:00")


def test_no_list_museum_gives_empty(client):
    body = client.get("/api/v1/museums/plain/must-see").json()
    assert body["items"] == []


def test_unknown_and_hidden_museum_404(client):
    assert client.get("/api/v1/museums/nope/must-see").status_code == 404
    assert client.get("/api/v1/museums/hidden/must-see").status_code == 404


def test_museum_list_has_must_see_count(client):
    rows = {r["slug"]: r for r in client.get("/api/v1/museums").json()}
    assert rows["orsay"]["must_see_count"] == 3
    assert rows["plain"]["must_see_count"] == 0
