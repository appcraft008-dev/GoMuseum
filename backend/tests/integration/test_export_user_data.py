"""GDPR 数据导出必须覆盖隐私政策声明保留的每一类个人数据。

隐私政策把「交易记录」明列为一类保留的个人数据,而这个函数一度只给
user / benefits / footprints —— 真拿它当"导出"用,就会漏掉一整类
自己声明要保留的东西。人工邮件流程下运营者能手动补,但那不是导出函数的合格线。
"""

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base
from app.models.purchase import Entitlement, Purchase
from app.models.recognition_event import RecognitionEvent
from app.models.user import User
from app.models.user_benefits import UserBenefits
from app.services.auth_service import AuthService


@pytest.fixture()
def db():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(
        bind=engine,
        tables=[
            User.__table__,
            UserBenefits.__table__,
            RecognitionEvent.__table__,
            Purchase.__table__,
            Entitlement.__table__,
        ],
    )
    session = sessionmaker(bind=engine)()
    yield session
    session.close()


@pytest.fixture()
def user(db):
    u = User(email="buyer@example.com", username="buyer", is_active=True)
    db.add(u)
    db.commit()
    db.refresh(u)
    return u


def _buy(db, uid, **kw):
    p = Purchase(
        user_id=str(uid),
        platform="google",
        product_id="paris_pass_7d",
        store_transaction_id=kw.pop("txn", "GPA.1234-5678"),
        amount=kw.pop("amount", None),
        currency=kw.pop("currency", "EUR"),
        status=kw.pop("status", "purchased"),
        receipt_payload='{"secret":"raw-google-receipt"}',
        **kw,
    )
    db.add(p)
    db.commit()
    return p


def test_导出包含购买与权益(db, user):
    _buy(db, user.id, amount=4.99, purchased_at=datetime.now(timezone.utc))
    db.add(
        Entitlement(
            user_id=str(user.id),
            entitlement_type="paris_pass_7d",
            status="active",
            granted_reason="purchase",
            expires_at=datetime.now(timezone.utc) + timedelta(days=7),
        )
    )
    db.commit()

    out = AuthService.export_user_data(db, user)

    assert len(out["purchases"]) == 1, "⭐ 隐私政策声明保留交易记录,导出就必须给"
    assert out["purchases"][0]["product_id"] == "paris_pass_7d"
    assert out["purchases"][0]["amount"] == "4.99"
    assert len(out["entitlements"]) == 1
    assert out["entitlements"][0]["status"] == "active"


def test_不导出原始收据(db, user):
    """receipt_payload 是 Google 签的凭据,对用户无意义、却可被重放。

    删号时的处理也是清掉它而保留账目本身 —— 两处判断要一致。
    """
    _buy(db, user.id)

    out = AuthService.export_user_data(db, user)

    assert "raw-google-receipt" not in str(out)
    assert "receipt_payload" not in out["purchases"][0]


def test_没买过的人导出空列表而不是缺字段(db, user):
    """前端/运营拿到的结构要稳定:没买过是空列表,不是这一节整个消失。"""
    out = AuthService.export_user_data(db, user)

    assert out["purchases"] == []
    assert out["entitlements"] == []


def test_只导出自己的交易(db, user):
    _buy(db, user.id, txn="GPA.mine")
    _buy(db, "someone-else", txn="GPA.theirs")

    out = AuthService.export_user_data(db, user)

    assert [p["store_transaction_id"] for p in out["purchases"]] == ["GPA.mine"]
