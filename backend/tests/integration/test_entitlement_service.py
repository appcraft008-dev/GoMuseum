"""统一权益判断:前端不得自行组合布尔值,一律问这里。

每条用例对应一个真实决策(见 memory monetization-plan):
购买不立即计时 / 到期不靠定时任务 / 首件语音按作品认领 / 免费 5 次。
"""

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import settings
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


def _ent(s, uid, status, expires=None):
    e = Entitlement(
        user_id=uid, entitlement_type="paris_pass_7d", status=status, expires_at=expires
    )
    s.add(e)
    s.commit()
    return e


def _ben(s, uid, used=0, quota=5, free_audio=None):
    b = UserBenefits(
        user_id=uid,
        recognition_quota=quota,
        total_recognitions_used=used,
        free_audio_qid=free_audio,
    )
    s.add(b)
    s.commit()
    return b


def test_no_purchase_is_not_purchased(session):
    assert es.resolve_state(session, "u1")[0] == es.NOT_PURCHASED


def test_purchase_does_not_start_the_clock(session):
    """⭐ 旅游产品必须这样:用户常提前几天买,立即计时会白烧有效期。"""
    _ent(session, "u1", es.PURCHASED_NOT_ACTIVATED)
    state, ent = es.resolve_state(session, "u1")
    assert state == es.PURCHASED_NOT_ACTIVATED
    assert ent.expires_at is None  # 还没开始计时


def test_activate_starts_7x24(session):
    _ent(session, "u1", es.PURCHASED_NOT_ACTIVATED)
    state, ent = es.activate(session, "u1")
    assert state == es.ACTIVE
    delta = ent.expires_at - ent.activated_at
    assert abs(delta - timedelta(days=7)) < timedelta(seconds=5)


def test_activate_is_idempotent(session):
    _ent(session, "u1", es.PURCHASED_NOT_ACTIVATED)
    _, first = es.activate(session, "u1")
    exp1 = first.expires_at
    _, again = es.activate(session, "u1")
    assert again.expires_at == exp1  # 再点不续期,也不重置


def test_expiry_computed_live_not_by_cron(session):
    """到期判断在读取时算 —— 依赖定时任务刷 status,漏跑就白送权限。"""
    past = datetime.now(timezone.utc) - timedelta(hours=1)
    _ent(session, "u1", es.ACTIVE, expires=past)
    assert es.resolve_state(session, "u1")[0] == es.EXPIRED


def test_free_user_recognition_quota(session):
    # recognition_quota 是**剩余数**(每次识别递减),不是上限——
    # 曾误算成 quota-used,会重复扣、让付费墙提前弹
    b = _ben(session, "u1", used=2, quota=5)
    out = es.summary(session, "u1", b)
    assert out["free_recognitions_left"] == 5, "剩余=quota本身,不该再减 used"
    assert out["can"]["recognize"] is True


def test_summary_reports_denominator_for_progress_ring(session):
    """前端进度环的分母由后端给,别让前端再写死一个 10。"""
    b = _ben(session, "u1", quota=2)
    b.referral_bonus_quota = 3
    session.commit()
    out = es.summary(session, "u1", b)
    assert out["free_recognitions_total"] == settings.FREE_RECOGNITION_QUOTA + 3
    assert out["free_recognitions_left"] == 5  # 2+3,不超过分母


def test_free_user_exhausted_cannot_recognize(session):
    b = _ben(session, "u1", used=5, quota=0)  # 递减到 0 才算用尽
    out = es.summary(session, "u1", b)
    assert out["free_recognitions_left"] == 0
    assert out["can"]["recognize"] is False


def test_active_pass_ignores_quota(session):
    _ent(
        session, "u1", es.ACTIVE, expires=datetime.now(timezone.utc) + timedelta(days=3)
    )
    b = _ben(session, "u1", used=99, quota=5)
    out = es.summary(session, "u1", b)
    assert out["can"]["recognize"] is True and out["can"]["audio_any"] is True
    assert out["free_recognitions_left"] is None  # 通票内不显示剩余次数


def test_free_audio_claimed_per_artwork_and_replayable(session):
    """首件按**作品**认领:该件可无限重播,第二件锁。"""
    b = _ben(session, "u1")
    assert es.claim_free_audio(session, b, "Q12418") is True
    assert es.can_play_audio(session, "u1", "Q12418", b) is True  # 可重播
    assert es.can_play_audio(session, "u1", "Q12418", b) is True
    assert es.can_play_audio(session, "u1", "Q151952", b) is False  # 第二件锁


def test_free_audio_cannot_be_claimed_twice(session):
    b = _ben(session, "u1")
    es.claim_free_audio(session, b, "Q1")
    assert es.claim_free_audio(session, b, "Q2") is False
    assert b.free_audio_qid == "Q1"


def test_referral_bonus_adds_to_quota(session):
    b = _ben(session, "u1", used=5, quota=2)
    b.referral_bonus_quota = 3
    session.commit()
    assert es.summary(session, "u1", b)["free_recognitions_left"] == 5  # 2+3


# —— 老权益兼容(2026-07-29):新付费规则不得让老用户失去已付费的权益 ——


def test_legacy_premium_grants_active_entitlement(session):
    """老用户 is_premium=True 但 entitlements 为空 → 补一张 ACTIVE 权益。

    不给 purchased_not_activated:他此前就在用,再要求点一次"开始计时"
    是凭空多出的坎,而且会让人以为票没了。
    """
    exp = datetime.now(timezone.utc) + timedelta(days=30)
    ent = es.grant_legacy_pass(
        session, user_id="u-legacy", kind=es.LEGACY_PREMIUM, expires_at=exp
    )
    assert ent.status == es.ACTIVE
    assert ent.scope == "*"  # 老权益无城市概念,覆盖全部
    assert ent.granted_reason == "legacy_migration"
    # 关键:音频闸门(只认 entitlements)现在放行
    state, _ = es.resolve_state(session, "u-legacy")
    assert state == es.ACTIVE


def test_legacy_pass_scope_covers_every_city(session):
    """scope='*' 必须覆盖任意城市 —— 老权益不该因为分城市 SKU 的引入而缩水。"""
    exp = datetime.now(timezone.utc) + timedelta(days=30)
    es.grant_legacy_pass(
        session, user_id="u-any", kind=es.LEGACY_PREMIUM, expires_at=exp
    )
    for city in ("Paris", "Madrid", "Amsterdam"):
        state, _ = es.resolve_state(session, "u-any", city)
        assert state == es.ACTIVE, city


def test_legacy_grant_is_idempotent(session):
    """重复跑迁移不发第二张(否则一次误重跑就白送一堆权益)。"""
    exp = datetime.now(timezone.utc) + timedelta(days=30)
    a = es.grant_legacy_pass(
        session, user_id="u-idem", kind=es.LEGACY_PREMIUM, expires_at=exp
    )
    b = es.grant_legacy_pass(
        session, user_id="u-idem", kind=es.LEGACY_PREMIUM, expires_at=exp
    )
    assert a.id == b.id
    assert session.query(Entitlement).filter_by(user_id="u-idem").count() == 1


def test_expired_legacy_premium_is_not_migrated(session):
    """已过期的老权益不搬 —— 搬过来也是 expired,只会让报表和状态机变脏。"""
    exp = datetime.now(timezone.utc) - timedelta(days=1)
    ent = es.grant_legacy_pass(
        session, user_id="u-expired", kind=es.LEGACY_PREMIUM, expires_at=exp
    )
    assert ent is None
    assert session.query(Entitlement).filter_by(user_id="u-expired").count() == 0
