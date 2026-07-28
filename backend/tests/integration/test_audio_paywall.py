"""语音付费墙的**执行点**在后端音频端点,不在前端 UI。

前端付费墙只是这道闸的表达:没有它,老 App / curl / 改客户端都能白拿音频,
而且每次都会触发 TTS 生成、花我们的钱。这里锁住闸门本身的四条规则。
"""

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base
from app.models.purchase import Entitlement, Purchase
from app.models.user_benefits import UserBenefits
from app.services import entitlement_service as es


@pytest.fixture()
def session():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(
        bind=engine,
        tables=[Purchase.__table__, Entitlement.__table__, UserBenefits.__table__],
    )
    yield sessionmaker(bind=engine)()


def _ben(s, uid="u1", free_audio=None):
    b = UserBenefits(user_id=uid, recognition_quota=5, free_audio_qid=free_audio)
    s.add(b)
    s.commit()
    return b


def test_first_artwork_is_claimed_and_allowed(session):
    """首件=**保证送达的首体验**,不是"一张待花的券"——券式设计下很多用户
    到最后压根没用过语音,付费墙就白建了。"""
    b = _ben(session)
    assert es.authorize_audio(session, "u1", "Q12418") is True
    session.refresh(b)
    assert b.free_audio_qid == "Q12418", "第一次请求就地认领"


def test_claimed_artwork_replays_forever(session):
    _ben(session, free_audio="Q12418")
    for _ in range(3):
        assert es.authorize_audio(session, "u1", "Q12418") is True


def test_second_artwork_is_denied(session):
    _ben(session, free_audio="Q12418")
    assert es.authorize_audio(session, "u1", "Q151952") is False


def test_active_pass_opens_everything(session):
    _ben(session, free_audio="Q12418")
    session.add(
        Entitlement(
            user_id="u1",
            entitlement_type="paris_pass_7d",
            status=es.ACTIVE,
            expires_at=datetime.now(timezone.utc) + timedelta(days=3),
        )
    )
    session.commit()
    assert es.authorize_audio(session, "u1", "Q151952") is True
    assert es.authorize_audio(session, "u1", "随便哪件") is True


def test_expired_pass_falls_back_to_free_rules(session):
    """到期在读取时实时判定 —— 靠定时任务刷状态,漏跑就白送权限。"""
    _ben(session, free_audio="Q12418")
    session.add(
        Entitlement(
            user_id="u1",
            entitlement_type="paris_pass_7d",
            status=es.ACTIVE,
            expires_at=datetime.now(timezone.utc) - timedelta(hours=1),
        )
    )
    session.commit()
    assert es.authorize_audio(session, "u1", "Q151952") is False
    assert es.authorize_audio(session, "u1", "Q12418") is True  # 首件仍可重播


def test_unknown_user_denied(session):
    """没有 benefits 行(伪造 user_id)不该白拿。"""
    assert es.authorize_audio(session, "查无此人", "Q12418") is False


def test_endpoint_actually_wires_the_gate():
    """接线测试:其余音频用例把闸门 no-op 掉了,这条确保端点**真的**挂着它。
    没有它,某次重构把 _require_audio_access 删了也不会有测试变红。"""
    from fastapi.testclient import TestClient

    from app.main import app

    for path in (
        "/api/v1/museums/orsay/objects/Q12418/audio",
        "/api/v1/museums/orsay/objects/Q12418/audio/stream",
    ):
        r = TestClient(app).get(path)
        assert r.status_code == 401, f"{path} 未鉴权就放行了: {r.status_code}"
        assert r.json()["detail"]["reason"] == "auth_required"
