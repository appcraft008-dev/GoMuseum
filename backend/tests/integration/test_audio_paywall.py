"""语音付费墙的**执行点**在后端音频端点,不在前端 UI。

前端付费墙只是这道闸的表达:没有它,老 App / curl / 改客户端都能白拿音频,
而且每次都会触发 TTS 生成、花我们的钱。这里锁住闸门本身的四条规则。
"""

from datetime import datetime, timedelta, timezone

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


def _ben(s, uid="u1", free_audio=None, lang="zh"):
    b = UserBenefits(
        user_id=uid,
        recognition_quota=5,
        free_audio_qid=free_audio,
        free_audio_lang=lang if free_audio else None,
    )
    s.add(b)
    s.commit()
    return b


def test_first_artwork_is_claimable_but_not_yet_claimed(session):
    """⚠️ 判定本身**不能有副作用**(2026-07-28 staging 实测踩到):
    闸门跑在生成之前,而生成可能 404(该语言没正文)/409/503。
    若在判定时就认领,用户点一件没音频的作品——什么都没听到,名额却没了。"""
    b = _ben(session)
    assert es.audio_access(session, "u1", "Q12418") == "claimable"
    session.refresh(b)
    assert b.free_audio_qid is None, "判定阶段绝不能认领"


def test_claim_happens_only_after_delivery(session):
    b = _ben(session)
    assert es.audio_access(session, "u1", "Q12418") == "claimable"
    assert es.claim_audio_now(session, "u1", "Q12418") is True  # 音频送达了
    session.refresh(b)
    assert b.free_audio_qid == "Q12418"
    assert es.audio_access(session, "u1", "Q12418") == "allowed"  # 之后可重播


def test_claimed_artwork_replays_forever(session):
    _ben(session, free_audio="Q12418")
    for _ in range(3):
        assert es.audio_access(session, "u1", "Q12418") == "allowed"


def test_second_artwork_is_denied(session):
    _ben(session, free_audio="Q12418")
    assert es.audio_access(session, "u1", "Q151952") == "denied"


def test_active_pass_opens_everything(session):
    _ben(session, free_audio="Q12418")
    session.add(
        Entitlement(
            user_id="u1",
            entitlement_type="paris_pass_7d",
            status=es.ACTIVE,
            expires_at=datetime.now(timezone.utc) + timedelta(days=3),
        )
    )
    session.commit()
    assert es.audio_access(session, "u1", "Q151952") == "allowed"
    assert es.audio_access(session, "u1", "随便哪件") == "allowed"


def test_expired_pass_falls_back_to_free_rules(session):
    """到期在读取时实时判定 —— 靠定时任务刷状态,漏跑就白送权限。"""
    _ben(session, free_audio="Q12418")
    session.add(
        Entitlement(
            user_id="u1",
            entitlement_type="paris_pass_7d",
            status=es.ACTIVE,
            expires_at=datetime.now(timezone.utc) - timedelta(hours=1),
        )
    )
    session.commit()
    assert es.audio_access(session, "u1", "Q151952") == "denied"
    assert es.audio_access(session, "u1", "Q12418") == "allowed"  # 首件仍可重播


def test_unknown_user_denied(session):
    """没有 benefits 行(伪造 user_id)不该白拿。"""
    assert es.audio_access(session, "查无此人", "Q12418") == "denied"


def test_endpoint_actually_wires_the_gate():
    """接线测试:其余音频用例把闸门 no-op 掉了,这条确保端点**真的**挂着它。
    没有它,某次重构把 _require_audio_access 删了也不会有测试变红。"""
    from fastapi.testclient import TestClient

    from app.main import app

    for path in (
        "/api/v1/museums/orsay/objects/Q12418/audio",
        "/api/v1/museums/orsay/objects/Q12418/audio/stream",
    ):
        r = TestClient(app).get(path)
        assert r.status_code == 401, f"{path} 未鉴权就放行了: {r.status_code}"
        assert r.json()["detail"]["reason"] == "auth_required"


def test_paywall_hit_is_recorded(session):
    """埋点此前**零调用方**:模型/迁移/ops_report 全建好了,但没人写入,
    付费漏斗报告永远是零。这条锁住撞墙确实留下痕迹。"""
    from app.models.app_event import AppEvent
    from app.services.event_log import log_event

    Base.metadata.create_all(bind=session.get_bind(), tables=[AppEvent.__table__])
    _ben(session, free_audio="Q12418")
    assert es.audio_access(session, "u1", "Q151952") == "denied"
    log_event(session, "paywall_viewed_from_audio", user_id="u1", qid="Q151952")

    ev = session.query(AppEvent).one()
    assert ev.name == "paywall_viewed_from_audio"
    assert ev.props["qid"] == "Q151952"


def test_content_endpoint_never_leaks_audio_urls():
    """⭐ 内容接口**无鉴权**(正文免费是策略),所以绝不能下发音频直链——
    发了等于把付费墙拆了:音频 key 做成不可推测(P0-b)也白搭,我们自己发出去。
    只给 has_audio 标志位,前端据此显示播放按钮,真要听走已加闸的 /audio。"""
    import inspect

    from app.services import museum_repo

    src = inspect.getsource(museum_repo.get_object_content)
    assert '"audio_url"' not in src, "内容接口不得下发音频直链"
    assert '"has_audio"' in src, "应改为只给标志位"


def test_tts_generate_requires_auth():
    """/content/tts/generate 此前完全没有鉴权:section 模式绕过 /audio 的闸,
    ad-hoc 模式接受任意文本 = 给全世界免费 TTS,账单算我们的。"""
    from fastapi.testclient import TestClient

    from app.main import app

    r = TestClient(app).post(
        "/api/v1/content/tts/generate",
        json={"text": "任意文本", "language": "zh"},
    )
    assert r.status_code == 401, f"未鉴权就放行了: {r.status_code}"
    assert r.json()["detail"]["reason"] == "auth_required"


def test_free_preview_is_one_artwork_one_language_one_section(session):
    """免费试听收敛到 (作品, 语言, 主讲解段)。

    一件作品还有背景/分析/问答/作者介绍等段落,每段独立 TTS,再乘 10 种语言——
    只按 qid 判的话"免费一件"实际是几十次生成,免费层成本失控。
    """
    _ben(session, free_audio="Q12418", lang="zh")
    # 同件同语言主讲解:可无限重播
    assert es.audio_access(session, "u1", "Q12418") == "allowed"
    # 同件但换语言 → 另一次 TTS,不在免费范围
    assert es.audio_access(session, "u1", "Q12418", language="fr") == "denied"
    # 同件同语言但深度段/问答/作者介绍 → 各自独立 TTS,属付费内容
    for sec in ("background", "analysis", "qa", "artist_bio"):
        assert (
            es.audio_access(session, "u1", "Q12418", section=sec) == "denied"
        ), f"{sec} 不该免费"


def test_claim_records_the_language(session):
    b = _ben(session)
    assert es.audio_access(session, "u1", "Q1", language="fr") == "claimable"
    es.claim_audio_now(session, "u1", "Q1", "fr")
    session.refresh(b)
    assert (b.free_audio_qid, b.free_audio_lang) == ("Q1", "fr")
    assert es.audio_access(session, "u1", "Q1", language="fr") == "allowed"
    assert es.audio_access(session, "u1", "Q1", language="zh") == "denied"


def test_deep_section_is_never_claimable(session):
    """深度段不能成为"首件" —— 否则用户在深度段用掉名额,主讲解反而听不了。"""
    _ben(session)
    assert es.audio_access(session, "u1", "Q1", section="analysis") == "denied"


def test_pass_scope_is_actually_enforced(session):
    """⭐ scope 此前存了却**从未被读过** —— 巴黎通票能解锁马德里。

    多城市那天才会发现,而那时已经在卖了。这条锁住它真的生效。
    """
    from datetime import datetime as _dt

    session.add(
        Entitlement(
            user_id="u1",
            entitlement_type="paris_pass_7d",
            scope="paris",
            status=es.ACTIVE,
            expires_at=_dt.now(timezone.utc) + timedelta(days=3),
        )
    )
    _ben(session)
    session.commit()

    assert es.resolve_state(session, "u1", "Paris")[0] == es.ACTIVE
    assert es.resolve_state(session, "u1", "Madrid")[0] == es.NOT_PURCHASED
    # 大小写不敏感
    assert es.resolve_state(session, "u1", "paris")[0] == es.ACTIVE
    # 音频闸跟着走:巴黎放行,马德里回落免费规则
    assert es.audio_access(session, "u1", "Q9", city="Paris") == "allowed"
    assert es.audio_access(session, "u1", "Q9", city="Madrid") == "claimable"


def test_product_catalog_drives_duration_and_scope(session):
    """新增 SKU 只改 PASSES 一行 —— 时长与 scope 都由目录决定,不是全局常量。"""
    assert es.is_pass_product("paris_pass_7d") is True
    assert es.is_pass_product("recognition_pack_10") is False, "老商品不该当通票"

    es.PASSES["madrid_pass_1d"] = {"days": 1, "scope": "madrid"}
    try:
        assert es.pass_duration("madrid_pass_1d") == timedelta(days=1)
        assert es.pass_scope("madrid_pass_1d") == "madrid"
        es.grant_from_purchase(
            session,
            user_id="u2",
            platform="android",
            product_id="madrid_pass_1d",
            store_transaction_id="t-madrid",
        )
        _, ent = es.activate(session, "u2")
        span = ent.expires_at - ent.activated_at
        assert span == timedelta(days=1), "1 日票不该发 7 天"
        assert ent.scope == "madrid"
        assert es.resolve_state(session, "u2", "Paris")[0] == es.NOT_PURCHASED
    finally:
        es.PASSES.pop("madrid_pass_1d", None)


def test_wildcard_scope_covers_every_city(session):
    """多国票:scope='*' 覆盖全部城市。"""
    assert es.covers_museum("*", "Madrid") is True
    assert es.covers_museum("*", None) is True
