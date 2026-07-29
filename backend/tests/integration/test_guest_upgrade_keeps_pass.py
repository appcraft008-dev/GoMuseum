"""游客买了通票后注册/登录,票必须跟着走。

这是**用户付了钱却拿不到东西**的那一类 bug,而且当时不会报错:
新建账号 → 新 user_id 查不到旧权益;想靠"恢复购买"补救也不行——
grant_from_purchase 靠 store_transaction_id 幂等,发现收据已存在就返回旧记录、
不给新用户发权益,接口却仍返回 verified=true。用户看到"购买成功",实际什么都没有。
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base, get_db
from app.main import app
from app.models.purchase import Entitlement, Purchase
from app.models.user import User
from app.models.user_benefits import UserBenefits
from app.services import entitlement_service as es


@pytest.fixture()
def client():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(
        bind=engine,
        tables=[
            User.__table__,
            UserBenefits.__table__,
            Purchase.__table__,
            Entitlement.__table__,
        ],
    )
    s = sessionmaker(bind=engine)()
    app.dependency_overrides[get_db] = lambda: s
    yield TestClient(app), s
    app.dependency_overrides.clear()
    s.close()


def _guest(c, device="dev-1"):
    r = c.post("/api/v1/auth/guest", json={"device_id": device})
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


def _uid(db, token):
    from app.services.auth_service import AuthService

    return str(AuthService.get_current_user(db, token).id)


def test_guest_upgrade_keeps_the_pass(client):
    """⭐ 核心:游客买票 → 注册 → 票还在。"""
    c, db = client
    token = _guest(c)
    guest_id = _uid(db, token)

    es.grant_from_purchase(
        db,
        user_id=guest_id,
        platform="android",
        product_id=es.PARIS_PASS_7D,
        store_transaction_id="txn-abc",
    )
    assert es.resolve_state(db, guest_id)[0] == es.PURCHASED_NOT_ACTIVATED

    r = c.post(
        "/api/v1/auth/register",
        json={
            "email": "a@b.com",
            "username": "someone",
            "password": "Passw0rd!123",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code in (200, 201), r.text

    new_id = _uid(db, r.json()["access_token"])
    assert new_id == guest_id, "必须就地转正(同一 UUID),否则票会凭空消失"
    assert es.resolve_state(db, new_id)[0] == es.PURCHASED_NOT_ACTIVATED


def test_upgrade_does_not_hand_out_a_second_free_quota(client):
    """换身份刷额度:游客 5 次 → 注册再 5 次。就地转正顺带堵住。"""
    c, db = client
    token = _guest(c, device="dev-2")
    guest_id = _uid(db, token)

    b = db.query(UserBenefits).filter_by(user_id=guest_id).one()
    b.recognition_quota = 1  # 已用掉 4 次
    db.commit()

    r = c.post(
        "/api/v1/auth/register",
        json={"email": "c@d.com", "username": "u2", "password": "Passw0rd!123"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code in (200, 201), r.text

    rows = db.query(UserBenefits).filter_by(user_id=guest_id).all()
    assert len(rows) == 1 and rows[0].recognition_quota == 1, "额度不该被重置"


def test_register_without_guest_token_still_creates_account(client):
    """没带游客令牌(全新安装直接注册)照旧新建,别把正常路径改坏。"""
    c, db = client
    r = c.post(
        "/api/v1/auth/register",
        json={"email": "e@f.com", "username": "u3", "password": "Passw0rd!123"},
    )
    assert r.status_code in (200, 201), r.text
    assert db.query(User).filter_by(email="e@f.com").one().is_guest is False


def test_guest_cannot_purchase(client):
    """买票前必须登录 —— 通票挂 user_id,而游客身份是**设备绑定**的:
    游客买了票,换手机/清数据就永久拿不回(收据已消耗,恢复购买命中幂等)。
    前端会先引导登录,但执行点在这里,不能只靠 UI 拦。"""
    c, db = client
    token = _guest(c, device="dev-3")
    r = c.post(
        "/api/v1/payment/verify",
        json={
            "platform": "android",
            "receipt_data": "fake",
            "product_id": "paris_pass_7d",
            "device_id": "dev-3",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 403, r.text
    assert r.json()["detail"]["reason"] == "login_required_to_purchase"


def test_entitlements_tell_frontend_whether_purchase_is_allowed(client):
    """前端只看 can —— 不自己拼身份判断(契约要求)。"""
    c, db = client
    token = _guest(c, device="dev-4")
    can = c.get(
        "/api/v1/entitlements/me", headers={"Authorization": f"Bearer {token}"}
    ).json()["can"]
    assert can["purchase"] is False, "游客不该看到直接购买入口"

    r = c.post(
        "/api/v1/auth/register",
        json={"email": "g@h.com", "username": "u4", "password": "Passw0rd!123"},
        headers={"Authorization": f"Bearer {token}"},
    )
    new_token = r.json()["access_token"]
    can2 = c.get(
        "/api/v1/entitlements/me", headers={"Authorization": f"Bearer {new_token}"}
    ).json()["can"]
    assert can2["purchase"] is True, "转正后应可购买"
