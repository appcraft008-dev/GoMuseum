"""付款 → 权益 的接线。两条 money-correctness 路径必须锁死:
重复上报不重复发放(恢复购买)、退款必须连权益一起撤(否则退了钱还能用)。
"""

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


def _grant(s, txn="txn-1", uid="u1"):
    return es.grant_from_purchase(
        s,
        user_id=uid,
        platform="google",
        product_id=es.PARIS_PASS_7D,
        store_transaction_id=txn,
        amount=7.99,
        currency="EUR",
    )


def test_purchase_creates_pass_but_does_not_start_clock(session):
    p, ent = _grant(session)
    assert p.status == "purchased"
    assert ent.status == es.PURCHASED_NOT_ACTIVATED
    assert ent.expires_at is None  # ⭐ 提前几天买不会白烧有效期
    assert es.resolve_state(session, "u1")[0] == es.PURCHASED_NOT_ACTIVATED


def test_same_transaction_never_grants_twice(session):
    """恢复购买会重复上报同一 token —— 重复发放 = 白送钱。"""
    _grant(session, txn="txn-1")
    _grant(session, txn="txn-1")
    _grant(session, txn="txn-1")
    assert session.query(Purchase).count() == 1
    assert session.query(Entitlement).count() == 1


def test_second_real_purchase_grants_again(session):
    """商品是 Consumable:明年再来巴黎要能再买(不同 txn = 新权益)。"""
    _grant(session, txn="txn-1")
    _grant(session, txn="txn-2")
    assert session.query(Purchase).count() == 2
    assert session.query(Entitlement).count() == 2


def test_refund_revokes_the_pass(session):
    """只标订单不撤权益 = 退了钱还能用。"""
    _grant(session, txn="txn-1")
    es.activate(session, "u1")
    assert es.resolve_state(session, "u1")[0] == es.ACTIVE

    assert es.revoke_for_purchase(session, "txn-1", "refunded") is True
    assert session.query(Purchase).one().status == "refunded"
    assert session.query(Entitlement).one().status == "refunded"
    # 撤销后不再是有效权益
    assert es.resolve_state(session, "u1")[0] == es.NOT_PURCHASED


def test_revoke_unknown_transaction_is_noop(session):
    assert es.revoke_for_purchase(session, "nope") is False


def test_activate_after_purchase_starts_7d(session):
    _grant(session)
    state, ent = es.activate(session, "u1")
    assert state == es.ACTIVE and ent.expires_at is not None
    assert es.summary(session, "u1")["can"]["audio_any"] is True
