"""
Integration tests for GDPR account deletion and data export endpoints
(App Store 账号删除硬性要求 + GDPR 数据可携权/删除权)
"""

import uuid

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


@pytest.fixture()
def client():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSession = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    # 只建本用例涉及的表（个别无关模型的 server_default NOW() 不兼容 SQLite）
    Base.metadata.create_all(
        bind=engine,
        tables=[
            User.__table__,
            UserBenefits.__table__,
            Purchase.__table__,
            Entitlement.__table__,
        ],
    )

    def override_get_db():
        db = TestingSession()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    yield TestClient(app)
    app.dependency_overrides.pop(get_db, None)


def _register(client, email="gdpr@test.com"):
    resp = client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "Test1234!", "username": "GDPR用户"},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


def test_export_my_data(client):
    tokens = _register(client)
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}

    resp = client.get("/api/v1/auth/me/export", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["user"]["email"] == "gdpr@test.com"
    assert data["user"]["username"] == "GDPR用户"
    assert isinstance(data["benefits"], list)


def test_delete_account_removes_user_and_benefits(client):
    tokens = _register(client)
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}
    user_id = tokens["user"]["id"]

    # 先给该用户造一条 benefits 记录
    db_gen = app.dependency_overrides[get_db]()
    db = next(db_gen)
    db.add(UserBenefits(user_id=user_id, recognition_quota=10))
    db.commit()

    resp = client.delete("/api/v1/auth/me", headers=headers)
    assert resp.status_code == 204

    assert db.query(User).filter(User.id == uuid.UUID(user_id)).first() is None
    assert (
        db.query(UserBenefits).filter(UserBenefits.user_id == user_id).first() is None
    )

    # 删除后原 token 失效（用户不存在）
    resp = client.get("/api/v1/auth/me", headers=headers)
    assert resp.status_code in (401, 404)

    # 同邮箱可重新注册
    resp = client.post(
        "/api/v1/auth/register",
        json={"email": "gdpr@test.com", "password": "Test1234!"},
    )
    assert resp.status_code == 201


def test_delete_requires_auth(client):
    resp = client.delete("/api/v1/auth/me")
    assert resp.status_code in (401, 403)


@pytest.fixture()
def client_db():
    """自带会话的 client(现有 fixture 只给 client,断言 DB 需要会话)。"""
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


def test_delete_revokes_entitlement_and_anonymizes_purchase(client_db):
    """删号时权益与订单性质不同,不能一起 delete 了事:

    - 权益**必须撤销** —— 人没了权益还"生效"是脏数据,此前完全没处理,
      通票会变成谁也用不了的孤儿。
    - 订单**保留但匿名化** —— 财务记录有会计/税务留存义务,不能删;
      但 receipt_payload 属个人数据,必须清空。
    """
    from app.services import entitlement_service as es
    from app.services.auth_service import AuthService

    c, db = client_db
    tok = c.post(
        "/api/v1/auth/register",
        json={
            "email": "del@gomuseum.app",
            "username": "del",
            "password": "Passw0rd!1",
        },
    ).json()["access_token"]
    uid = str(AuthService.get_current_user(db, tok).id)

    es.grant_from_purchase(
        db,
        user_id=uid,
        platform="android",
        product_id=es.PARIS_PASS_7D,
        store_transaction_id="txn-del",
        receipt_payload="SENSITIVE",
    )

    r = c.delete("/api/v1/auth/me", headers={"Authorization": f"Bearer {tok}"})
    assert r.status_code == 204, r.text

    ents = db.query(Entitlement).all()
    assert ents and all(e.status == "revoked" for e in ents), "权益必须撤销"
    p = db.query(Purchase).filter_by(store_transaction_id="txn-del").one()
    assert p.receipt_payload is None, "个人数据必须清除"
    assert p.user_id.startswith("deleted:"), "关联切断,财务记录保留"
