"""Google 审核/测试机器人(Play 预发布报告、审核员)从 Google 网段登录,
打 probe_login 标,运营报告把它们和测试账号从「真实用户」里剔除。

10-30 实测:近 7 天 34 个活跃身份里约 25 个来自 Google 网段,真实外部只有 3 个。
"""

from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base, get_db
from app.main import app
from app.models.app_event import AppEvent
from app.models.llm_usage import LLMUsage
from app.models.museum import Museum
from app.models.museum_object import MuseumObject
from app.models.object_embedding import ObjectEmbedding
from app.models.purchase import Entitlement, Purchase
from app.models.recognition_demand import RecognitionDemand
from app.models.recognition_event import RecognitionEvent
from app.models.user import User
from app.models.user_benefits import UserBenefits
from app.services.event_log import is_google_probe_ip
from scripts.ops_report import build


@pytest.fixture()
def Session():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(
        bind=engine,
        tables=[
            User.__table__,
            UserBenefits.__table__,
            AppEvent.__table__,
            Museum.__table__,
            MuseumObject.__table__,
            Purchase.__table__,
            Entitlement.__table__,
            RecognitionEvent.__table__,
            RecognitionDemand.__table__,
            LLMUsage.__table__,
            ObjectEmbedding.__table__,
        ],
    )
    S = sessionmaker(bind=engine, autoflush=False, autocommit=False)

    def override():
        db = S()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override
    yield S
    app.dependency_overrides.pop(get_db, None)


@pytest.mark.parametrize(
    "ip,expected",
    [
        ("66.249.88.46", True),
        ("74.125.212.40", True),
        ("66.102.7.164", True),
        ("192.178.11.34", True),
        ("90.160.64.195", False),  # 西班牙家宽
        ("185.5.129.26", False),  # Lebara 手机
        (None, False),
        ("testclient", False),
    ],
)
def test_is_google_probe_ip(ip, expected):
    assert is_google_probe_ip(ip) is expected


def _guest(ip, device):
    c = TestClient(app, client=(ip, 50000))
    r = c.post("/api/v1/auth/guest", json={"device_id": device})
    assert r.status_code == 200, r.text
    return r.json()["user"]["id"]


def test_guest_from_google_ip_marked(Session):
    uid = _guest("74.125.209.36", "dev-bot")
    db = Session()
    ev = db.query(AppEvent).filter(AppEvent.name == "probe_login").one()
    assert ev.user_id == str(uid) and ev.device_id == "dev-bot"


def test_guest_from_normal_ip_not_marked(Session):
    _guest("185.5.129.26", "dev-real")
    db = Session()
    assert db.query(AppEvent).filter(AppEvent.name == "probe_login").count() == 0


def test_report_real_users_exclude_probe_and_test(Session):
    db = Session()
    db.add_all(
        [
            # 真实用户:账号 + 只有设备的游客
            AppEvent(name="content_viewed", user_id="real1"),
            AppEvent(name="guest_created", device_id="dev-real2"),
            # 机器人:账号被标过,它的设备事件也不算
            AppEvent(name="probe_login", user_id="bot1", device_id="dev-bot1"),
            AppEvent(name="content_viewed", user_id="bot1"),
            AppEvent(name="guest_created", device_id="dev-bot1"),
            # 测试账号(许可测试单)
            Purchase(
                user_id="tester",
                platform="google",
                product_id="paris_pass_7d",
                store_transaction_id="t1",
                is_test=True,
            ),
            AppEvent(name="content_viewed", user_id="tester"),
            RecognitionEvent(
                phash="p", outcome="match", engine="vector", user_id="real3"
            ),
            RecognitionEvent(
                phash="p", outcome="match", engine="vector", user_id="bot1"
            ),
        ]
    )
    db.commit()
    ru = build(db, 7)["real_users"]
    assert ru == {"active": 3, "probe": 1, "test": 1}, ru
