"""
Integration tests for auth security hardening:
refresh token rotation (旧 refresh token 用过即作废)
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


def test_refresh_token_rotation(client):
    resp = client.post(
        "/api/v1/auth/register",
        json={"email": "rotate@test.com", "password": "Test1234!"},
    )
    assert resp.status_code == 201
    old_refresh = resp.json()["refresh_token"]

    # 第一次刷新成功，拿到新 token 对
    resp = client.post("/api/v1/auth/refresh", json={"refresh_token": old_refresh})
    assert resp.status_code == 200
    new_refresh = resp.json()["refresh_token"]
    assert new_refresh != old_refresh

    # 旧 refresh token 已被轮换撤销，再次使用必须失败
    resp = client.post("/api/v1/auth/refresh", json={"refresh_token": old_refresh})
    assert resp.status_code == 401

    # 新 refresh token 仍然可用
    resp = client.post("/api/v1/auth/refresh", json={"refresh_token": new_refresh})
    assert resp.status_code == 200


def test_refresh_rejects_access_token(client):
    resp = client.post(
        "/api/v1/auth/register",
        json={"email": "rotate2@test.com", "password": "Test1234!"},
    )
    access = resp.json()["access_token"]

    resp = client.post("/api/v1/auth/refresh", json={"refresh_token": access})
    assert resp.status_code == 401
