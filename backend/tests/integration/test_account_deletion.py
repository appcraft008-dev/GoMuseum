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
