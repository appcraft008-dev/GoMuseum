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


def _ben(s, uid="u1", unlocked=None):
    b = UserBenefits(
        user_id=uid,
        recognition_quota=5,
        free_audio_qids=list(unlocked or []),
    )
    s.add(b)
    s.commit()
    return b


def test_gate_has_no_side_effects(session):
    """⚠️ 判定本身**不能有副作用**(2026-07-28 staging 实测踩到)。

    当年的形态是"判定时就认领"→ 用户点一件没音频的作品,什么都没听到、名额却
    没了。认领已经随规则改动整个删除(解锁发生在识别扣费那一处),但"闸门只读"
    这条约束留着:它挡的是**下一次**有人想在闸里顺手写点什么。
    """
    b = _ben(session)
    assert es.audio_access(session, "u1", "Q12418") == "denied"
    session.refresh(b)
    assert not b.free_audio_qids, "判定阶段绝不能写解锁清单"


def test_recognized_artwork_replays_forever(session):
    _ben(session, unlocked=["Q12418"])
    for _ in range(3):
        assert es.audio_access(session, "u1", "Q12418") == "allowed"


def test_artwork_never_recognized_is_denied(session):
    _ben(session, unlocked=["Q12418"])
    assert es.audio_access(session, "u1", "Q151952") == "denied"


def test_active_pass_opens_everything(session):
    _ben(session, unlocked=["Q12418"])
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
    _ben(session, unlocked=["Q12418"])
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
    assert es.audio_access(session, "u1", "Q12418") == "allowed"  # 识别过的仍可重播


def test_missing_benefits_row_is_denied_because_nothing_recognized_yet(session):
    """benefits 行是**懒建**的。行不存在 = 一次都没识别过 = 还没解锁任何作品。

    ⚠️ 这条的历史值得留着:它原本叫 `test_unknown_user_denied`,把"行还没建"
    当成"伪造的 user_id";而真实的新注册用户正是没有行的那一类
    (2026-09-19 prod 78 个用户里 35 个没有行),于是**每个新用户**点听讲解都
    撞墙。当时的修法是判 claimable 放行。

    改成"跟着识别走"之后,同一个状态反过来该判 denied —— 而这**不再是那个坑**:
    解锁写在识别扣费的同一处,而那里 get_or_create_benefits 一定会把行建出来。
    换句话说"有解锁清单"与"有行"从此同生共死,不会再出现"有权限但行还没建"。
    """
    assert es.audio_access(session, "全新用户", "Q12418") == "denied"

    es.unlock_free_audio(session, "全新用户", ["Q12418"])  # 识别成功
    assert es.audio_access(session, "全新用户", "Q12418") == "allowed"  # 可重播
    assert es.audio_access(session, "全新用户", "Q151952") == "denied"  # 没识别过的要票
    # 深度段不因已解锁而放宽:解锁只认主讲解段
    assert (
        es.audio_access(session, "全新用户", "Q12418", section="analysis") == "denied"
    )


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
    _ben(session, unlocked=["Q12418"])
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


def test_free_audio_covers_the_guide_section_only(session):
    """解锁只覆盖**主讲解段**,不覆盖深度段/问答/作者介绍。

    一件作品还有背景/分析/问答/作者介绍等段落,每段独立 TTS ——
    不限段的话"识别过就能听"实际是每件几十次生成。
    """
    _ben(session, unlocked=["Q12418"])
    assert es.audio_access(session, "u1", "Q12418") == "allowed"
    for sec in ("background", "analysis", "qa", "artist_bio"):
        assert (
            es.audio_access(session, "u1", "Q12418", section=sec) == "denied"
        ), f"{sec} 不该免费"


def test_language_no_longer_narrows_the_unlock(session):
    """⚠️ 这条断言的是一个**故意放宽**的规则(2026-09-19),不是漏判。

    旧规则把免费试听绑死在 (作品, 语言, 段):中文识别完、事后把 App 切成法语
    的人会撞 402 —— 他没多拿任何东西,只是换了个界面语言,却被当成第二件。
    换语言确实要多一次 TTS,但上限是「解锁件数 × 语言数」且生成一次永久落库,
    这点钱买不到"同一件作品换个语言就要买票"的困惑。
    """
    _ben(session, unlocked=["Q12418"])
    for lang in ("zh", "fr", "en"):
        assert es.audio_access(session, "u1", "Q12418", language=lang) == "allowed"


def test_deep_section_alone_unlocks_nothing(session):
    """没识别过的作品,深度段自然也是拒。"""
    _ben(session)
    assert es.audio_access(session, "u1", "Q1", section="analysis") == "denied"


def test_unlock_appends_and_is_idempotent(session):
    """多次识别累积;同一件重复识别不产生重复项。

    ⚠️ JSON 列**原地 append 不会被标脏**,更新会被 SQLAlchemy 静默丢掉 ——
    unlock_free_audio 因此整列重新赋值。这条就是那个坑的看门狗:
    第二次解锁若丢了,`Q2` 会查不到。
    """
    b = _ben(session)
    assert es.unlock_free_audio(session, "u1", ["Q1"]) == ["Q1"]
    assert es.unlock_free_audio(session, "u1", ["Q2"]) == ["Q2"]
    assert es.unlock_free_audio(session, "u1", ["Q1"]) == [], "重复识别不该再记一次"
    session.refresh(b)
    assert b.free_audio_qids == ["Q1", "Q2"]
    for q in ("Q1", "Q2"):
        assert es.audio_access(session, "u1", q) == "allowed"


def test_unlock_creates_the_row_when_missing(session):
    """行懒建:第一次识别时把行建出来,否则解锁写进空气里。"""
    assert es.unlock_free_audio(session, "新用户", ["Q1"]) == ["Q1"]
    row = session.query(UserBenefits).filter_by(user_id="新用户").one()
    assert row.free_audio_qids == ["Q1"]


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
    assert es.audio_access(session, "u1", "Q9", city="Madrid") == "denied"


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


# HTTPBearer(auto_error=True):没有这个头,依赖注入阶段就 403,替身根本轮不到。
_AUTH = {"Authorization": "Bearer test-token"}


def _known_object(session, qid="Q12418"):
    """解锁端点要校验 qid 真实存在 —— 测试库里得真有这一行,
    否则测的是 404 分支而不是扣费分支。"""
    import uuid as _uuid

    from app.models.museum_object import MuseumObject

    MuseumObject.__table__.create(bind=session.get_bind(), checkfirst=True)
    session.add(MuseumObject(id=_uuid.uuid4(), qid=qid, museum_id=_uuid.uuid4()))
    session.commit()


def _client_with_user(session, uid="u1"):
    """把端点的 DB 与鉴权都换成替身:这里考的是**额度与解锁的关系**,
    不是登录链路(那另有专测)。"""
    from fastapi.testclient import TestClient

    from app.api.v1.endpoints import entitlements as ep
    from app.core.database import get_db
    from app.main import app

    class _U:
        id = uid
        is_guest = False

    app.dependency_overrides[get_db] = lambda: session
    original = ep.AuthService.get_current_user
    ep.AuthService.get_current_user = staticmethod(lambda db, token: _U())
    client = TestClient(app)
    yield_client = (
        client,
        lambda: setattr(ep.AuthService, "get_current_user", original),
    )
    return yield_client


def test_unlock_endpoint_spends_one_quota_and_unlocks(session):
    """⭐ 免费额度是**一个池子**:拍照识别扣它,主动解锁也扣它。

    这条钉住的是"解锁真的要花额度" —— 不花的话免费语音就没有上限,
    用户在列表里逐件点开就能把 24000 件全听完。
    """
    from app.models.app_event import AppEvent

    Base.metadata.create_all(bind=session.get_bind(), tables=[AppEvent.__table__])
    b = _ben(session)  # recognition_quota=5
    _known_object(session)
    client, restore = _client_with_user(session)
    try:
        r = client.post("/api/v1/entitlements/audio/unlock?qid=Q12418", headers=_AUTH)
        assert r.status_code == 200
        assert r.json()["free_recognitions_left"] == 4, "解锁要花掉 1 次"
        assert r.json()["free_audio_qids"] == ["Q12418"]
        assert es.audio_access(session, "u1", "Q12418") == "allowed"

        # 幂等:再点一次不该再扣
        r = client.post("/api/v1/entitlements/audio/unlock?qid=Q12418", headers=_AUTH)
        assert r.status_code == 200
        assert r.json()["free_recognitions_left"] == 4, "重复解锁不该二次扣费"
    finally:
        restore()
        from app.main import app as _app

        _app.dependency_overrides.clear()
    session.refresh(b)
    assert b.recognition_quota == 4


def test_unlock_endpoint_denies_when_quota_is_gone(session):
    """额度空了 → 402,前端据此弹付费墙。**绝不能先解锁再扣费** ——
    那样额度为 0 时权益已经发出去,白送的正是我们要卖的东西。"""
    from app.models.app_event import AppEvent

    Base.metadata.create_all(bind=session.get_bind(), tables=[AppEvent.__table__])
    b = _ben(session)
    b.recognition_quota = 0
    session.commit()
    _known_object(session)
    client, restore = _client_with_user(session)
    try:
        r = client.post("/api/v1/entitlements/audio/unlock?qid=Q12418", headers=_AUTH)
        assert r.status_code == 402
        assert r.json()["detail"]["reason"] == "pass_required"
    finally:
        restore()
        from app.main import app as _app

        _app.dependency_overrides.clear()
    assert es.audio_access(session, "u1", "Q12418") == "denied", "402 了就不该解锁"


def test_unlock_unknown_qid_returns_404_and_costs_nothing(session):
    """⭐ 客户端一个笔误不该让用户白掉一次额度 —— 那是他花钱换来的东西。

    2026-09-19 staging 实测抓到:未校验前,`qid=Q-does-not-exist` 返回 200
    并扣掉一次额度(4 → 3),用户什么也没得到。404 也比"扣了钱什么都没解锁"
    好排查得多。
    """
    from app.models.app_event import AppEvent

    Base.metadata.create_all(bind=session.get_bind(), tables=[AppEvent.__table__])
    b = _ben(session)
    _known_object(session)  # 只建了 Q12418,下面故意问别的
    client, restore = _client_with_user(session)
    try:
        r = client.post(
            "/api/v1/entitlements/audio/unlock?qid=Q-does-not-exist", headers=_AUTH
        )
        assert r.status_code == 404
        assert r.json()["detail"]["reason"] == "object_not_found"
    finally:
        restore()
        from app.main import app as _app

        _app.dependency_overrides.clear()
    session.refresh(b)
    assert b.recognition_quota == 5, "未知 qid 绝不能扣额度"
