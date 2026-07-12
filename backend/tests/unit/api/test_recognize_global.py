"""全局识别端点 POST /api/v1/recognize + 老端点内部委托 的 API 层测试。

service 层(recognize_billed)整体 monkeypatch:本层只验路由/参数/错误映射,
不重复 service 的识别逻辑测试(见 tests/integration/test_recognize_flow.py)。
"""

import pytest
from fastapi.testclient import TestClient

from app.core.database import get_db
from app.main import app
from app.services.recognition.service import QuotaExceededError


@pytest.fixture()
def client():
    app.dependency_overrides[get_db] = lambda: iter([object()])
    yield TestClient(app)
    app.dependency_overrides.pop(get_db, None)


def _img():
    return {"image": ("a.jpg", b"fake-bytes", "image/jpeg")}


def test_global_recognize_calls_service_with_slug_none(client, monkeypatch):
    seen = {}

    def fake(db, slug, data, **kw):
        seen["slug"] = slug
        return {"outcome": "match", "match": {"qid": "Q1"}}

    monkeypatch.setattr("app.services.recognition.service.recognize_billed", fake)

    r = client.post("/api/v1/recognize?device_id=dev-1", files=_img())
    assert r.status_code == 200, r.text
    assert r.json()["outcome"] == "match"
    assert seen["slug"] is None


def test_museum_param_scopes_to_slug(client, monkeypatch):
    seen = {}

    def fake(db, slug, data, **kw):
        seen["slug"] = slug
        return {"outcome": "candidates", "candidates": []}

    monkeypatch.setattr("app.services.recognition.service.recognize_billed", fake)

    r = client.post("/api/v1/recognize?museum=orsay&device_id=dev-1", files=_img())
    assert r.status_code == 200, r.text
    assert seen["slug"] == "orsay"


def test_unknown_museum_returns_404(client, monkeypatch):
    monkeypatch.setattr(
        "app.services.recognition.service.recognize_billed",
        lambda db, slug, data, **kw: None,
    )
    r = client.post("/api/v1/recognize?museum=nope&device_id=dev-1", files=_img())
    assert r.status_code == 404


def test_quota_exceeded_returns_402(client, monkeypatch):
    def fake(db, slug, data, **kw):
        raise QuotaExceededError()

    monkeypatch.setattr("app.services.recognition.service.recognize_billed", fake)
    r = client.post("/api/v1/recognize?device_id=dev-1", files=_img())
    assert r.status_code == 402
    assert r.json()["detail"]["reason"] == "quota_exceeded"


def test_identity_required_when_anonymous(client, monkeypatch):
    monkeypatch.setattr(
        "app.services.recognition.service.recognize_billed",
        lambda *a, **k: {"outcome": "match"},
    )
    r = client.post("/api/v1/recognize", files=_img())
    assert r.status_code == 401


def test_old_museum_endpoint_still_200_and_passthrough(client, monkeypatch):
    payload = {"outcome": "match", "match": {"qid": "Q7"}, "extra": 1}
    seen = {}

    def fake(db, slug, data, **kw):
        seen["slug"] = slug
        return payload

    monkeypatch.setattr("app.services.recognition.service.recognize_billed", fake)

    r = client.post("/api/v1/museums/orsay/recognize?device_id=dev-1", files=_img())
    assert r.status_code == 200, r.text
    assert r.json() == payload
    assert seen["slug"] == "orsay"


# --- POST /recognize/confirm(回填 confirmed_qid,fire-and-forget 恒 204) ---


def _confirm_client():
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.pool import StaticPool

    from app.core.database import Base
    from app.models.museum import Museum
    from app.models.museum_object import MuseumObject, ObjectImage
    from app.models.recognition_event import RecognitionEvent
    from app.services.object_importer import upsert_museum, upsert_object

    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(
        bind=engine,
        tables=[
            Museum.__table__,
            MuseumObject.__table__,
            ObjectImage.__table__,
            RecognitionEvent.__table__,
        ],
    )
    s = sessionmaker(bind=engine)()
    m = upsert_museum(s, {"slug": "orsay", "name_en": "Orsay"})
    upsert_object(s, m.id, {"qid": "Q1", "title_en": "A"})
    s.commit()

    def _override():
        yield s

    app.dependency_overrides[get_db] = _override
    return TestClient(app), s


def test_confirm_backfills_recent_event():
    from app.models.recognition_event import RecognitionEvent

    client, s = _confirm_client()
    try:
        s.add(
            RecognitionEvent(
                museum_slug="orsay",
                phash="ph1",
                outcome="candidates",
                top_qid="Q1",
                engine="text",
            )
        )
        s.commit()
        r = client.post("/api/v1/recognize/confirm", json={"phash": "ph1", "qid": "Q1"})
        assert r.status_code == 204
        s.expire_all()
        row = s.query(RecognitionEvent).filter_by(phash="ph1").one()
        assert row.confirmed_qid == "Q1"
    finally:
        app.dependency_overrides.pop(get_db, None)


def test_confirm_garbage_phash_still_204():
    client, s = _confirm_client()
    try:
        r = client.post(
            "/api/v1/recognize/confirm", json={"phash": "nope", "qid": "Q1"}
        )
        assert r.status_code == 204
    finally:
        app.dependency_overrides.pop(get_db, None)


def test_confirm_unknown_qid_ignored_but_204():
    from app.models.recognition_event import RecognitionEvent

    client, s = _confirm_client()
    try:
        s.add(
            RecognitionEvent(
                museum_slug="orsay", phash="ph2", outcome="candidates", engine="text"
            )
        )
        s.commit()
        r = client.post(
            "/api/v1/recognize/confirm", json={"phash": "ph2", "qid": "Q_NOPE"}
        )
        assert r.status_code == 204
        s.expire_all()
        row = s.query(RecognitionEvent).filter_by(phash="ph2").one()
        assert row.confirmed_qid is None
    finally:
        app.dependency_overrides.pop(get_db, None)
