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


def _ent(s, uid, status, expires=None, created=None):
    e = Entitlement(
        user_id=uid, entitlement_type="paris_pass_7d", status=status, expires_at=expires
    )
    if created is not None:
        e.created_at = created  # 测未激活票的保质期要能把购买时刻推到过去
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


# ── 未激活票的保质期(买了不激活,30 天后作废) ──


def test_unactivated_pass_expires_after_the_window(session):
    """未激活票此前**永不过期** = 每笔收入背一份无限期负债。"""
    bought = datetime.now(timezone.utc) - es.ACTIVATION_WINDOW - timedelta(hours=1)
    _ent(session, "u1", es.PURCHASED_NOT_ACTIVATED, created=bought)
    assert es.resolve_state(session, "u1")[0] == es.EXPIRED


def test_unactivated_pass_survives_right_up_to_the_deadline(session):
    """差一小时到期仍然可用 —— 边界错一天就是白没收一个用户的票。"""
    bought = datetime.now(timezone.utc) - es.ACTIVATION_WINDOW + timedelta(hours=1)
    _ent(session, "u1", es.PURCHASED_NOT_ACTIVATED, created=bought)
    assert es.resolve_state(session, "u1")[0] == es.PURCHASED_NOT_ACTIVATED


def test_expired_unactivated_pass_cannot_be_activated(session):
    """过保质期的票不能再激活 —— 否则窗口形同虚设。"""
    bought = datetime.now(timezone.utc) - es.ACTIVATION_WINDOW - timedelta(days=1)
    e = _ent(session, "u1", es.PURCHASED_NOT_ACTIVATED, created=bought)
    state, _ = es.activate(session, "u1")
    assert state == es.EXPIRED
    session.refresh(e)
    assert e.status == es.PURCHASED_NOT_ACTIVATED and e.expires_at is None


def test_expired_unactivated_pass_does_not_shadow_a_new_one(session):
    """过期的旧票不能挡住续购的新票 —— 挡住了就是"付了第二次钱也用不了"。"""
    old = datetime.now(timezone.utc) - es.ACTIVATION_WINDOW - timedelta(days=5)
    _ent(session, "u1", es.PURCHASED_NOT_ACTIVATED, created=old)
    _ent(session, "u1", es.PURCHASED_NOT_ACTIVATED, created=datetime.now(timezone.utc))
    assert es.resolve_state(session, "u1")[0] == es.PURCHASED_NOT_ACTIVATED
    assert es.activate(session, "u1")[0] == es.ACTIVE


def test_missing_created_at_never_forfeits_the_pass(session):
    """拿不到购买时刻就**不没收**:漏没收只是少赚,错没收是拿了钱不给货。"""
    e = _ent(session, "u1", es.PURCHASED_NOT_ACTIVATED)
    e.created_at = None
    session.commit()
    assert es.resolve_state(session, "u1")[0] == es.PURCHASED_NOT_ACTIVATED
    assert es.activation_deadline(e) is None


def test_summary_tells_the_frontend_when_the_pass_lapses(session):
    """前端要能显示「X 月 X 日前激活」,否则用户不知道票在倒计时。"""
    bought = datetime.now(timezone.utc) - timedelta(days=2)
    _ent(session, "u1", es.PURCHASED_NOT_ACTIVATED, created=bought)
    out = es.summary(session, "u1", _ben(session, "u1"))
    assert out["state"] == es.PURCHASED_NOT_ACTIVATED
    assert out["activate_by"] is not None
    lapse = datetime.fromisoformat(out["activate_by"])
    assert abs(lapse - (bought + es.ACTIVATION_WINDOW)) < timedelta(seconds=5)


def test_activate_by_is_absent_once_the_clock_runs(session):
    """已激活的票没有"激活截止" —— 留着会让前端显示一个无意义的日期。"""
    _ent(
        session, "u1", es.ACTIVE, expires=datetime.now(timezone.utc) + timedelta(days=3)
    )
    assert es.summary(session, "u1", _ben(session, "u1"))["activate_by"] is None


# ── 票据历史(权益页的「购买记录」与「上一张票」) ──


def test_history_gives_each_pass_its_own_outcome(session):
    """历史要的是**每张票各自的结局**,不是"当前哪张说了算"。"""
    now = datetime.now(timezone.utc)
    _ent(
        session,
        "u1",
        es.ACTIVE,
        expires=now - timedelta(days=1),
        created=now - timedelta(days=8),
    )  # 用完的旧票
    _ent(session, "u1", es.PURCHASED_NOT_ACTIVATED, created=now)  # 新买的
    rows = es.history(session, "u1")
    assert [r["state"] for r in rows] == [es.PURCHASED_NOT_ACTIVATED, es.EXPIRED]
    assert rows[0]["purchased_at"] is not None


def test_history_marks_lapsed_unactivated_as_expired(session):
    """过保质期的未激活票在历史里也是 expired,不能显示成"还能用"。"""
    bought = datetime.now(timezone.utc) - es.ACTIVATION_WINDOW - timedelta(days=1)
    _ent(session, "u1", es.PURCHASED_NOT_ACTIVATED, created=bought)
    assert es.history(session, "u1")[0]["state"] == es.EXPIRED


def test_history_keeps_refunded_rows_visible(session):
    """退款的票不隐藏 —— 用户问"我的钱去哪了"时,这一行就是答案。"""
    _ent(session, "u1", "refunded")
    assert es.history(session, "u1")[0]["state"] == "refunded"


def test_history_is_per_user(session):
    _ent(session, "u1", es.PURCHASED_NOT_ACTIVATED)
    _ent(session, "u2", es.PURCHASED_NOT_ACTIVATED)
    assert len(es.history(session, "u1")) == 1


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
