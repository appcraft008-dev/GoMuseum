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
    from app.models.purchase import Entitlement
    from app.models.recognition_event import RecognitionEvent
    from app.models.user_benefits import UserBenefits
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
            # 确认要计费(2026-09-20 起),于是这条路上要问额度表与通票表。
            UserBenefits.__table__,
            Entitlement.__table__,
        ],
    )
    s = sessionmaker(bind=engine)()
    m = upsert_museum(s, {"slug": "orsay", "name_en": "Orsay"})
    upsert_object(s, m.id, {"qid": "Q1", "title_en": "A"})
    upsert_object(s, m.id, {"qid": "Q2", "title_en": "B"})
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


# --- 确认即计费(2026-09-20:候选态的唯一扣费点) ---


def _as_user(monkeypatch, uid="u-1"):
    """令牌恒解析成 uid —— 连 Bearer 这一段一起覆盖,不跳过 _user_id。"""

    class _U:
        id = uid

    from app.services.auth_service import AuthService

    monkeypatch.setattr(AuthService, "get_current_user", lambda db, tok: _U())
    return {"Authorization": "Bearer t"}


def _event(s, phash, qid="Q1"):
    from app.models.recognition_event import RecognitionEvent

    s.add(
        RecognitionEvent(
            museum_slug="orsay",
            phash=phash,
            outcome="candidates",
            top_qid=qid,
            engine="text",
        )
    )
    s.commit()


def test_confirm_charges_one_and_unlocks_audio(monkeypatch):
    """点选候选 = 确认识别成功 → 扣 1 次 + 解锁这件的语音(与 match 同价)。"""
    from app.core.config import settings
    from app.models.user_benefits import UserBenefits
    from app.services import entitlement_service as es

    client, s = _confirm_client()
    headers = _as_user(monkeypatch)
    try:
        _event(s, "ph-pay")
        r = client.post(
            "/api/v1/recognize/confirm",
            json={"phash": "ph-pay", "qid": "Q1"},
            headers=headers,
        )
        assert r.status_code == 204
        s.expire_all()
        b = s.query(UserBenefits).filter_by(user_id="u-1").one()
        assert b.recognition_quota == settings.FREE_RECOGNITION_QUOTA - 1
        assert es.audio_access(s, "u-1", "Q1") == "allowed"
    finally:
        app.dependency_overrides.pop(get_db, None)


def test_confirm_same_photo_twice_charges_once(monkeypatch):
    """⭐ 一次拍照只扣一次 —— 候选恰恰是"没把握"的那一档,点错再回去点另一个很常见。

    第二行事件模拟重拍同一张图(命中识别缓存也会再落一行):幂等判据若只看
    "最新那行确认没有",这里就会扣第二次。
    """
    from app.core.config import settings
    from app.models.user_benefits import UserBenefits
    from app.services import entitlement_service as es

    client, s = _confirm_client()
    headers = _as_user(monkeypatch)
    try:
        _event(s, "ph-same")
        client.post(
            "/api/v1/recognize/confirm",
            json={"phash": "ph-same", "qid": "Q1"},
            headers=headers,
        )
        _event(s, "ph-same")  # 重拍/缓存命中,同 phash 再落一行
        client.post(
            "/api/v1/recognize/confirm",
            json={"phash": "ph-same", "qid": "Q2"},
            headers=headers,
        )
        s.expire_all()
        b = s.query(UserBenefits).filter_by(user_id="u-1").one()
        assert b.recognition_quota == settings.FREE_RECOGNITION_QUOTA - 1
        # 改主意选了另一件:不再扣费,**也不白送解锁**。
        # 端点不知道这次识别给了哪几个候选(事件行只存 top_qid),放行的话
        # qid 可以任填 —— 确认过一次就能拿一次额度解锁全馆。
        # 真想听第二件:详情页点播放会弹手动解锁确认(那里明写"将用掉 1 次")。
        assert es.audio_access(s, "u-1", "Q2") == "denied"
    finally:
        app.dependency_overrides.pop(get_db, None)


def test_confirm_anonymous_charges_nothing():
    """无令牌:照旧回填埋点,但不扣任何人的额度(解锁的语音也无处兑现)。"""
    from app.models.recognition_event import RecognitionEvent
    from app.models.user_benefits import UserBenefits

    client, s = _confirm_client()
    try:
        _event(s, "ph-anon")
        r = client.post(
            "/api/v1/recognize/confirm", json={"phash": "ph-anon", "qid": "Q1"}
        )
        assert r.status_code == 204
        s.expire_all()
        assert s.query(UserBenefits).count() == 0
        row = s.query(RecognitionEvent).filter_by(phash="ph-anon").one()
        assert row.confirmed_qid == "Q1"
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
