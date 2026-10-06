"""S5 照片反馈端点。照片只进私有桶;未配置/开关关时整体不可用(隐私政策上线前的闸)。"""

import io

import pytest
from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import settings
from app.core.database import get_db
from app.main import app
from app.models.recognition_event import RecognitionEvent
from app.models.recognition_photo_feedback import KEY_PREFIX, RecognitionPhotoFeedback
from app.services.storage import photo_feedback as pf


class _FakeStore:
    def __init__(self):
        self.objs = {}

    def put(self, key, data, content_type):
        self.objs[key] = data

    def delete(self, key):
        self.objs.pop(key, None)


def _jpeg(size=(32, 32)):
    buf = io.BytesIO()
    Image.new("RGB", size, (200, 10, 10)).save(buf, format="JPEG")
    return buf.getvalue()


@pytest.fixture()
def env(monkeypatch):
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    RecognitionPhotoFeedback.__table__.create(bind=engine)
    RecognitionEvent.__table__.create(bind=engine)
    s = sessionmaker(bind=engine)()
    store = _FakeStore()
    monkeypatch.setattr(settings, "PHOTO_FEEDBACK_ENABLED", True)
    monkeypatch.setattr(pf, "get_photo_feedback_storage", lambda: store)
    app.dependency_overrides[get_db] = lambda: s
    yield TestClient(app), s, store
    app.dependency_overrides.clear()
    s.close()


def _post(client, image=None, **fields):
    data = {"trigger": "found", "phash": "ph1", **fields}
    return client.post(
        "/api/v1/feedback/recognition-photo",
        data=data,
        files={"image": ("x.jpg", image or _jpeg(), "image/jpeg")},
    )


def test_anonymous_upload_goes_to_private_bucket(env):
    client, s, store = env
    r = _post(client, answer_qid="Q1", museum_slug="orsay", text="说明牌在右边")
    assert r.status_code == 204
    row = s.query(RecognitionPhotoFeedback).one()
    assert row.image_key.startswith(KEY_PREFIX)
    assert list(store.objs) == [row.image_key]
    assert row.trigger == "found" and row.answer_qid == "Q1"
    assert row.user_id is None
    assert row.engine_model == settings.RECOG_MODEL
    assert row.status == "new"


def test_server_result_comes_from_event_not_client(env):
    client, s, _ = env
    s.add(
        RecognitionEvent(
            phash="ph1",
            outcome="candidates",
            top_qid="Q9",
            top_score=0.8,
            engine="vector",
            rejected_qids=["Q9"],
        )
    )
    s.commit()
    _post(client)
    row = s.query(RecognitionPhotoFeedback).one()
    assert row.server_result["top_qid"] == "Q9"
    assert row.server_result["rejected_qids"] == ["Q9"]


def test_upload_503_when_bucket_unconfigured(env, monkeypatch):
    client, s, _ = env
    monkeypatch.setattr(pf, "get_photo_feedback_storage", lambda: None)
    assert _post(client).status_code == 503
    assert s.query(RecognitionPhotoFeedback).count() == 0


def test_upload_503_when_switch_off(env, monkeypatch):
    client, s, _ = env
    monkeypatch.setattr(settings, "PHOTO_FEEDBACK_ENABLED", False)
    assert _post(client).status_code == 503


def test_rejects_non_image(env):
    client, s, store = env
    assert _post(client, image=b"not an image").status_code == 422
    assert not store.objs


def test_rejects_oversized(env, monkeypatch):
    client, s, store = env
    monkeypatch.setattr(settings, "PHOTO_FEEDBACK_MAX_BYTES", 100)
    assert _post(client).status_code == 413
    assert not store.objs


def test_rejects_unknown_trigger(env):
    client, _, store = env
    assert _post(client, trigger="whatever").status_code == 422
    assert not store.objs


def test_storage_failure_leaves_no_row(env, monkeypatch):
    """桶写失败:不能留下一行指向不存在对象的记录;返回 5xx 让 App 重试一次。"""
    client, s, store = env

    def boom(*a, **k):
        raise ConnectionError("r2 down")

    monkeypatch.setattr(store, "put", boom)
    assert _post(client).status_code == 503
    assert s.query(RecognitionPhotoFeedback).count() == 0


def test_recognize_flag_off_when_unconfigured(monkeypatch):
    monkeypatch.setattr(settings, "PHOTO_FEEDBACK_ENABLED", True)
    monkeypatch.setattr(pf, "get_photo_feedback_storage", lambda: None)
    assert pf.photo_feedback_available() is False
    monkeypatch.setattr(pf, "get_photo_feedback_storage", lambda: _FakeStore())
    assert pf.photo_feedback_available() is True
    monkeypatch.setattr(settings, "PHOTO_FEEDBACK_ENABLED", False)
    assert pf.photo_feedback_available() is False


def test_private_storage_uses_its_own_endpoint(monkeypatch):
    """EU 管辖权桶只能走 `<账号>.eu.r2.cloudflarestorage.com`(公开桶的普通地址对它 AccessDenied,
    2026-10-06 实测)。私有桶必须用自己的 endpoint,不能借公开桶的。"""
    captured = {}

    class _R2:
        def __init__(self, endpoint_url, *a):
            captured["endpoint"] = endpoint_url

    import app.services.storage.r2 as r2

    monkeypatch.setattr(r2, "R2ObjectStorage", _R2)
    monkeypatch.setattr(pf, "_instance", None)
    monkeypatch.setattr(settings, "R2_ENDPOINT_URL", "https://acct.r2.example")
    monkeypatch.setattr(
        settings, "PHOTO_FEEDBACK_R2_ENDPOINT_URL", "https://acct.eu.r2.example"
    )
    monkeypatch.setattr(settings, "PHOTO_FEEDBACK_R2_BUCKET", "b")
    monkeypatch.setattr(settings, "PHOTO_FEEDBACK_R2_ACCESS_KEY_ID", "k")
    monkeypatch.setattr(settings, "PHOTO_FEEDBACK_R2_SECRET_ACCESS_KEY", "s")
    assert pf.get_photo_feedback_storage() is not None
    assert captured["endpoint"] == "https://acct.eu.r2.example"
    monkeypatch.setattr(pf, "_instance", None)
