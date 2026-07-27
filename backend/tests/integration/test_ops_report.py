"""运营报告:不建后台,一条命令出数。

重点验两件容易错的:①按馆归因(全局识别端点导致 museum_slug 为空,必须按命中
对象归因)②跨馆复用率(MVP 最重要的新指标)。
"""

from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base
from app.models.app_event import AppEvent
from app.models.museum import Museum
from app.models.museum_object import MuseumObject
from app.models.purchase import Entitlement, Purchase
from app.models.recognition_demand import RecognitionDemand
from app.models.recognition_event import RecognitionEvent
from app.models.user_benefits import UserBenefits
from app.services.object_importer import upsert_museum, upsert_object
from scripts.ops_report import build


@pytest.fixture()
def session():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(
        bind=engine,
        tables=[
            Museum.__table__,
            MuseumObject.__table__,
            AppEvent.__table__,
            Purchase.__table__,
            Entitlement.__table__,
            UserBenefits.__table__,
            RecognitionEvent.__table__,
            RecognitionDemand.__table__,
        ],
    )
    s = sessionmaker(bind=engine)()
    m = upsert_museum(s, {"slug": "louvre", "name_en": "L"})
    upsert_object(s, m.id, {"qid": "Q12418", "title_en": "Mona Lisa", "attributes": {}})
    s.commit()
    yield s


def test_recognition_attributed_by_matched_object(session):
    """全局识别端点让 museum_slug 为空 —— 必须按命中对象归因,否则全落"未归因"。"""
    session.add(
        RecognitionEvent(
            museum_slug=None,
            phash="p",
            outcome="match",
            top_qid="Q12418",
            engine="vector",
        )
    )
    session.commit()
    r = build(session, 7)
    assert "louvre" in r["recognition_by_museum"], r["recognition_by_museum"]
    assert r["recognition_by_museum"]["louvre"]["match"] == 1


def test_cross_museum_reuse_rate(session):
    for uid, slugs in [("u1", ["louvre", "orsay"]), ("u2", ["louvre"])]:
        for s in slugs:
            session.add(AppEvent(name="museum_used", user_id=uid, museum_slug=s))
    session.commit()
    cm = build(session, 7)["cross_museum"]
    assert cm["users"] == 2 and cm["multi"] == 1 and cm["reuse_pct"] == 50.0


def test_funnel_and_purchase_trigger(session):
    session.add(AppEvent(name="free_quota_exhausted", user_id="u1"))
    session.add(AppEvent(name="paywall_viewed_from_audio", user_id="u1"))
    session.add(
        AppEvent(name="purchase_succeeded", user_id="u1", props={"trigger": "audio"})
    )
    session.commit()
    r = build(session, 7)
    assert r["funnel"]["free_quota_exhausted"] == 1
    assert r["funnel"]["paywall_viewed_from_audio"] == 1
    assert r["purchase_triggers"]["audio"] == 1


def test_demand_top_is_refill_priority(session):
    # RecognitionDemand 对 phash 有唯一约束(同一张照片不重复记需求)——
    # 三个不同用户拍同一件 = 三个不同 phash
    for i in range(3):
        session.add(
            RecognitionDemand(
                museum_slug="louvre", phash=f"p{i}", label_text="La Joconde"
            )
        )
    session.commit()
    assert build(session, 7)["demand_top"][0] == ("La Joconde", 3)


def test_revenue_counts_only_purchased(session):
    session.add(
        Purchase(
            user_id="u1",
            platform="google",
            product_id="p",
            store_transaction_id="t1",
            amount=7.99,
            status="purchased",
            purchased_at=datetime.now(timezone.utc),
        )
    )
    session.add(
        Purchase(
            user_id="u2",
            platform="google",
            product_id="p",
            store_transaction_id="t2",
            amount=7.99,
            status="refunded",
        )
    )
    session.commit()
    assert build(session, 7)["revenue_eur"] == 7.99  # 退款不计收入
