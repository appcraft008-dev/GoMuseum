"""OAuth 按邮箱认领已有账号时的抢注防护。

注册**不要求**证明你拥有那个邮箱。所以在这道防护之前:
攻击者拿 victim@gmail.com 注册 → 机主日后用 Google 登录 → 后端按邮箱认领到
攻击者那一行 → 两人共用同一个账号,攻击者知道密码,机主买的通票他也能用。

堵法不是"拒绝认领"(email 是 unique 列,拒绝 = 把合法机主永远锁在门外),
而是作废那行**从没被证明过**的密码凭据 —— OAuth 这侧刚刚证明了邮箱所有权。
"""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base
from app.core.security import hash_password, verify_password
from app.models.user import User
from app.services.auth_service import AuthService


@pytest.fixture()
def db():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine, tables=[User.__table__])
    session = sessionmaker(bind=engine, autoflush=False, autocommit=False)()
    yield session
    session.close()


def _user(db, *, email, verified, password="squatter-pw"):
    u = User(
        email=email,
        username="whoever",
        password_hash=hash_password(password),
        is_active=True,
        is_verified=verified,
    )
    db.add(u)
    db.commit()
    db.refresh(u)
    return u


@pytest.mark.parametrize("field,pid", [("google_id", "g-123"), ("apple_id", "a-456")])
def test_未验证的抢注行被认领时密码作废(db, field, pid):
    # 攻击者注册了机主的邮箱(没验证,也无从验证——他收不到那封信)
    squatted = _user(db, email="victim@gmail.com", verified=False)

    AuthService._link_oauth_to_existing(squatted, field, pid)
    db.commit()

    assert getattr(squatted, field) == pid, "机主必须能认领回自己的邮箱"
    assert (
        squatted.password_hash is None
    ), "⭐ 攻击者知道的那个密码必须失效 —— 留着它,机主买的通票攻击者照样能用"
    assert squatted.is_verified is True


@pytest.mark.parametrize("field,pid", [("google_id", "g-123"), ("apple_id", "a-456")])
def test_已验证的真机主绑OAuth时密码保留(db, field, pid):
    # 机主自己先注册、点过验证信,后来才绑 Google/Apple
    owner = _user(db, email="owner@gmail.com", verified=True, password="my-real-pw")

    AuthService._link_oauth_to_existing(owner, field, pid)
    db.commit()

    assert getattr(owner, field) == pid
    assert owner.password_hash is not None, "⭐ 已证明过邮箱所有权的人不该被没收密码"
    assert verify_password("my-real-pw", owner.password_hash)


def test_登录端点认清密码后的账号(db):
    """作废密码不是摆设:login 必须真的挡住。"""
    from fastapi import HTTPException

    from app.schemas.auth import LoginRequest

    squatted = _user(db, email="victim@gmail.com", verified=False)
    AuthService._link_oauth_to_existing(squatted, "google_id", "g-123")
    db.commit()

    with pytest.raises(HTTPException) as e:
        AuthService.login(
            db, LoginRequest(email="victim@gmail.com", password="squatter-pw")
        )
    assert e.value.status_code == 401
