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
    assert ru == {"active": 3, "probe": 1, "test": 1, "tester": 0}, ru


# ── 自己人的测试机(10-31):移动网络 IP 每次都变,靠账号/设备标记;家和办公室 IP 兜底 ──


def test_guest_from_tester_ip_marked(Session, monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "OPS_TESTER_IPS", "84.123.20.145, 90.160.64.195")
    uid = _guest("84.123.20.145", "dev-home")
    _guest("185.5.129.26", "dev-real")
    db = Session()
    ev = db.query(AppEvent).filter(AppEvent.name == "tester_mark").one()
    assert ev.user_id == str(uid) and ev.device_id == "dev-home"


def test_mark_testers_script(Session):
    from scripts.mark_testers import mark

    db = Session()
    db.add(User(email="me@example.com", username="me"))
    db.commit()
    uid = str(db.query(User).one().id)
    assert mark(db, emails=["me@example.com"], devices=["dev-old"]) == 2
    assert mark(db, emails=["me@example.com"], devices=["dev-old"]) == 0  # 重跑不重复写
    rows = {(e.user_id, e.device_id) for e in db.query(AppEvent)}
    assert rows == {(uid, None), (None, "dev-old")}
    with pytest.raises(SystemExit):
        mark(db, emails=["nobody@example.com"], devices=[])


def test_report_excludes_testers_across_devices_and_accounts(Session):
    db = Session()
    db.add_all(
        [
            AppEvent(name="tester_mark", user_id="me"),
            AppEvent(name="tester_mark", device_id="dev-wife"),
            # 我的账号在新手机上(移动网络,没被 IP 标)→ 账号已标,这台设备上的游客也算自己人
            AppEvent(name="content_viewed", user_id="me", device_id="dev-new"),
            AppEvent(name="guest_created", device_id="dev-new"),
            UserBenefits(user_id="guest-on-new", device_id="dev-new"),
            AppEvent(name="content_viewed", user_id="guest-on-new"),
            # 老婆旧手机:设备已标,上面登录的 Google 账号也算自己人
            UserBenefits(user_id="wife", device_id="dev-wife"),
            RecognitionEvent(
                phash="p", outcome="match", engine="vector", user_id="wife"
            ),
            # 真实用户
            AppEvent(name="content_viewed", user_id="real1"),
        ]
    )
    db.commit()
    ru = build(db, 7)["real_users"]
    assert ru == {"active": 1, "probe": 0, "test": 0, "tester": 3}, ru


def test_shared_build_id_device_does_not_drag_in_real_users(Session):
    """老版本 App 把 Build.ID(同 ROM 全相同)当 device_id —— 不能拿它连坐陌生人。"""
    db = Session()
    db.add_all(
        [
            AppEvent(name="tester_mark", user_id="me"),
            UserBenefits(user_id="me", device_id="AQ3A.250226.002"),
            UserBenefits(user_id="stranger", device_id="AQ3A.250226.002"),
            AppEvent(name="content_viewed", user_id="stranger"),
            AppEvent(name="content_viewed", user_id="me"),
        ]
    )
    db.commit()
    ru = build(db, 7)["real_users"]
    assert ru["active"] == 1 and ru["tester"] == 1, ru
