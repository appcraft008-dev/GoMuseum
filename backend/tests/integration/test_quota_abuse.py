"""
Integration tests for quota anti-abuse:
- 同一设备重复游客登录复用账号（卸载重装不重置额度）
- benefits / consume 必须携带有效 token
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base, get_db
from app.main import app
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
    Base.metadata.create_all(
        bind=engine,
        tables=[User.__table__, UserBenefits.__table__],
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


def test_guest_login_reuses_account_for_same_device(client):
    resp1 = client.post("/api/v1/auth/guest", json={"device_id": "device-abc"})
    assert resp1.status_code == 200, resp1.text
    user1 = resp1.json()["user"]["id"]

    # 模拟卸载重装后再次游客登录：同一设备返回同一账号
    resp2 = client.post("/api/v1/auth/guest", json={"device_id": "device-abc"})
    assert resp2.status_code == 200
    assert resp2.json()["user"]["id"] == user1

    # 不同设备是新账号
    resp3 = client.post("/api/v1/auth/guest", json={"device_id": "device-xyz"})
    assert resp3.json()["user"]["id"] != user1


def test_benefits_and_consume_require_auth(client):
    assert client.get("/api/v1/payment/benefits").status_code in (401, 403)
    assert client.post("/api/v1/payment/consume").status_code in (401, 403)


def test_consume_decrements_account_quota(client):
    token = client.post("/api/v1/auth/guest", json={"device_id": "device-q"}).json()[
        "access_token"
    ]
    headers = {"Authorization": f"Bearer {token}"}

    before = client.get(
        "/api/v1/payment/benefits?device_id=device-q", headers=headers
    ).json()
    assert before["total_quota"] == 10

    resp = client.post("/api/v1/payment/consume?device_id=device-q", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["remaining_quota"] == 9

    # 重新游客登录（同设备）后额度仍是 9，而不是回到 10
    token2 = client.post("/api/v1/auth/guest", json={"device_id": "device-q"}).json()[
        "access_token"
    ]
    after = client.get(
        "/api/v1/payment/benefits?device_id=device-q",
        headers={"Authorization": f"Bearer {token2}"},
    ).json()
    assert after["total_quota"] == 9
