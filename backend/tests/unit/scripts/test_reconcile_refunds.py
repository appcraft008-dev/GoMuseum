"""退款对账脚本。

钉住的不是"能跑通",而是几条**撤错票**与**假绿**的具体形态:
  - 查不到 ≠ 已退款(不能凭问不出来没收用户的票)
  - 没凭证时必须失败,不能报成"0 笔退款"
  - 批量撤销要有闸(Play 换语义/配错包名 = 一整批看起来全退了)
"""

import uuid

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base
from app.models.purchase import Entitlement, Purchase
from app.services import entitlement_service as es
from scripts.reconcile_refunds import NoCredentials, reconcile


@pytest.fixture()
def db():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(
        bind=engine, tables=[Purchase.__table__, Entitlement.__table__]
    )
    session = sessionmaker(bind=engine, autoflush=False, autocommit=False)()
    yield session
    session.close()


class FakeIAP:
    """只替掉"去问 Play"这一处。[answers] 按 purchase_token 给回答。"""

    def __init__(self, answers: dict, *, has_token: bool = True):
        self.answers = answers
        self._has_token = has_token
        self.asked: list[str] = []

    def _play_access_token(self):
        return "fake-token" if self._has_token else None

    async def verify_google_receipt(self, purchase_token, product_id, **_):
        self.asked.append(purchase_token)
        return self.answers[purchase_token]


PURCHASED = {"valid": True, "status": 0}
CANCELED = {"valid": False, "status": 1}
API_DOWN = {"valid": False, "error": "play_api_500"}
NOT_FOUND = {"valid": False, "error": "play_api_404"}


def _buy(
    db, *, token, order, ent_status=es.PURCHASED_NOT_ACTIVATED, platform="android"
):
    p = Purchase(
        id=uuid.uuid4(),
        user_id=f"u-{order}",
        platform=platform,
        product_id="paris_pass_7d",
        store_transaction_id=order,
        status="purchased",
        receipt_payload=token,
    )
    db.add(p)
    db.flush()
    ent = Entitlement(
        id=uuid.uuid4(),
        user_id=p.user_id,
        entitlement_type="paris_pass_7d",
        scope="paris",
        source_purchase_id=p.id,
        status=ent_status,
    )
    db.add(ent)
    db.commit()
    return p, ent


async def test_refunded_purchase_is_revoked(db):
    p, ent = _buy(db, token="tok-refunded", order="GPA.REFUND")

    report = await reconcile(db, FakeIAP({"tok-refunded": CANCELED}), apply=True)

    assert report["refunded"] == ["GPA.REFUND"]
    assert report["applied"] is True
    db.refresh(ent)
    db.refresh(p)
    # 权益必须真的撤掉 —— 只标订单不撤权益 = 退了钱还能用满 7 天(I10)
    assert ent.status == "refunded"
    assert p.status == "refunded"


async def test_dry_run_reports_but_changes_nothing(db):
    _, ent = _buy(db, token="tok-refunded", order="GPA.REFUND")

    report = await reconcile(db, FakeIAP({"tok-refunded": CANCELED}))

    assert report["refunded"] == ["GPA.REFUND"]
    assert report["applied"] is False
    db.refresh(ent)
    assert ent.status == es.PURCHASED_NOT_ACTIVATED


async def test_healthy_purchase_untouched(db):
    _, ent = _buy(db, token="tok-ok", order="GPA.OK")

    report = await reconcile(db, FakeIAP({"tok-ok": PURCHASED}), apply=True)

    assert report["ok"] == 1 and report["refunded"] == []
    db.refresh(ent)
    assert ent.status == es.PURCHASED_NOT_ACTIVATED


@pytest.mark.parametrize("answer", [API_DOWN, NOT_FOUND], ids=["api_down", "not_found"])
async def test_unanswerable_is_never_treated_as_refund(db, answer):
    """**查不到 ≠ 已退款。** 拿"问不出来"去撤票 = 凭故障没收用户已付的东西。

    404 也在内:token 未知与 token 过期无法区分,而两者一个该撤一个绝不该撤。
    """
    _, ent = _buy(db, token="tok-x", order="GPA.X")

    report = await reconcile(db, FakeIAP({"tok-x": answer}), apply=True)

    assert report["refunded"] == []
    assert len(report["unknown"]) == 1
    db.refresh(ent)
    assert ent.status == es.PURCHASED_NOT_ACTIVATED


async def test_exception_on_one_purchase_does_not_stop_the_rest(db):
    class Boom(FakeIAP):
        async def verify_google_receipt(self, purchase_token, product_id, **_):
            if purchase_token == "tok-boom":
                raise RuntimeError("socket exploded")
            return await super().verify_google_receipt(purchase_token, product_id)

    _buy(db, token="tok-boom", order="GPA.BOOM")
    _, ent2 = _buy(db, token="tok-refunded", order="GPA.REFUND")

    report = await reconcile(
        db, Boom({"tok-refunded": CANCELED}), apply=True, max_revoke_ratio=1.0
    )

    assert len(report["unknown"]) == 1
    db.refresh(ent2)
    assert ent2.status == "refunded"


async def test_missing_credentials_fails_loudly(db):
    """没凭证时**必须抛**。返回一份"0 笔退款"的干净报告是最坏的结果 ——
    一个从来没真正跑起来的对账任务会天天绿着。"""
    _buy(db, token="tok-ok", order="GPA.OK")

    iap = FakeIAP({}, has_token=False)
    with pytest.raises(NoCredentials):
        await reconcile(db, iap, apply=True)
    assert iap.asked == []  # 一笔都没问,更不可能撤


async def test_mass_revoke_is_blocked_by_ratio_guard(db):
    """Play 换语义 / 包名配错 → 一整批"看起来全退款了"。宁可一笔不撤。"""
    ents = []
    for i in range(4):
        _, ent = _buy(db, token=f"tok-{i}", order=f"GPA.{i}")
        ents.append(ent)

    answers = {f"tok-{i}": CANCELED for i in range(4)}
    report = await reconcile(db, FakeIAP(answers), apply=True, max_revoke_ratio=0.2)

    assert report["aborted"] and report["applied"] is False
    for ent in ents:
        db.refresh(ent)
        assert ent.status == es.PURCHASED_NOT_ACTIVATED


async def test_lone_paying_user_refund_still_gets_revoked(db):
    """**只有一个活跃付费用户时,他退款就是 100%。**

    纯比例闸会把这一笔挡下 —— 而那正是上线头几个月的常态,等于对账脚本
    从第一天起就不生效,还绿着(报告写"已中止,等人确认",没人会去确认)。
    绝对下限就是为这条存在的。
    """
    _, ent = _buy(db, token="tok-only", order="GPA.ONLY")

    report = await reconcile(db, FakeIAP({"tok-only": CANCELED}), apply=True)

    assert report["aborted"] is None
    db.refresh(ent)
    assert ent.status == "refunded"


async def test_only_live_entitlements_are_scanned(db):
    """已过期/已撤销的票不必对账 —— 退不退款都改变不了什么。

    这条同时是**成本闸**:扫描量恒等于活跃付费用户数,不随历史订单增长。
    """
    _buy(db, token="tok-live", order="GPA.LIVE", ent_status=es.ACTIVE)
    _buy(db, token="tok-dead", order="GPA.DEAD", ent_status="expired")
    _buy(db, token="tok-gone", order="GPA.GONE", ent_status="revoked")

    iap = FakeIAP({"tok-live": PURCHASED})
    report = await reconcile(db, iap)

    assert iap.asked == ["tok-live"]
    assert report["scanned"] == 1


async def test_ios_purchases_are_not_asked_of_play(db):
    """苹果的收据拿去问 Play 只会得到 404 → 计入 unknown → 每次对账都告警。"""
    _buy(db, token="tok-ios", order="1000000123", platform="ios")

    iap = FakeIAP({})
    report = await reconcile(db, iap)

    assert iap.asked == []
    assert report["scanned"] == 0
