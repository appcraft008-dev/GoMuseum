"""收据校验与退款撤销 —— 付费链路最容易白送钱的两处。

⚠️ 此前 verify_google_receipt 是 **mock**:对任何 purchase_token 都返回
valid=True,任何登录用户 POST 一个编造的 receipt_data 就能白拿 €7.99 通票;
且不返回 transaction_id → 幂等键回落成客户端提供的字符串 → 无限刷票。
"""

import base64
import json

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import settings
from app.core.database import Base, get_db
from app.main import app
from app.models.purchase import Entitlement, Purchase
from app.models.user import User
from app.models.user_benefits import UserBenefits
from app.services import entitlement_service as es
from app.services.iap_verification_service import IAPVerificationService


@pytest.fixture()
def client():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(
        bind=engine,
        tables=[
            User.__table__,
            UserBenefits.__table__,
            Purchase.__table__,
            Entitlement.__table__,
        ],
    )
    s = sessionmaker(bind=engine)()
    app.dependency_overrides[get_db] = lambda: s
    yield TestClient(app), s
    app.dependency_overrides.clear()
    s.close()


@pytest.mark.asyncio
async def test_unconfigured_play_credentials_reject_not_allow(monkeypatch):
    """没有服务账号 = 无法证明这笔购买真实存在 → **拒绝**,绝不当作有效。

    这正是 mock 版最致命的地方:它在凭证缺失时返回 valid=True。
    """
    monkeypatch.setattr(settings, "GOOGLE_PLAY_SERVICE_ACCOUNT", None)
    out = await IAPVerificationService().verify_google_receipt(
        purchase_token="随便编的", product_id="paris_pass_7d"
    )
    assert out["valid"] is False
    assert out["error"] == "google_play_not_configured"


def test_fake_receipt_grants_nothing(client):
    """端到端:伪造收据拿不到通票(凭证未配置时全部拒绝)。"""
    c, db = client
    tok = c.post(
        "/api/v1/auth/register",
        json={"email": "b@gomuseum.app", "username": "b", "password": "Passw0rd!1"},
    ).json()["access_token"]

    r = c.post(
        "/api/v1/payment/verify",
        json={
            "platform": "android",
            "receipt_data": "完全编造的凭证",
            "product_id": "paris_pass_7d",
            "device_id": "d1",
        },
        headers={"Authorization": f"Bearer {tok}"},
    )
    assert r.json()["verified"] is False, "伪造收据绝不能通过"
    assert db.query(Entitlement).count() == 0, "没通过就不该有权益"


def test_refund_revokes_the_entitlement(client):
    """退款必须连权益一起撤 —— 只标订单退款、留着 entitlement 生效
    = 退了钱还能用满 7 天。revoke_for_purchase 早写好了,此前**零调用方**。"""
    c, db = client
    es.grant_from_purchase(
        db,
        user_id="u1",
        platform="android",
        product_id=es.PARIS_PASS_7D,
        store_transaction_id="GPA.1234",
    )
    es.activate(db, "u1")
    assert es.resolve_state(db, "u1")[0] == es.ACTIVE

    assert es.revoke_for_purchase(db, "GPA.1234", reason="refunded") is True
    assert es.resolve_state(db, "u1")[0] == es.NOT_PURCHASED, "退款后不该还生效"


def _rtdn(order_id: str) -> dict:
    body = {"voidedPurchaseNotification": {"orderId": order_id}}
    return {"message": {"data": base64.b64encode(json.dumps(body).encode()).decode()}}


def test_rtdn_requires_shared_token(client, monkeypatch):
    """回调是公网端点,没密钥就拒绝一切请求,不裸奔。"""
    c, _ = client
    monkeypatch.setattr(settings, "PLAY_RTDN_TOKEN", "s3cret")
    assert c.post("/api/v1/payment/rtdn", json=_rtdn("X")).status_code == 403
    assert (
        c.post("/api/v1/payment/rtdn?token=wrong", json=_rtdn("X")).status_code == 403
    )


def test_rtdn_voided_purchase_revokes(client, monkeypatch):
    c, db = client
    monkeypatch.setattr(settings, "PLAY_RTDN_TOKEN", "s3cret")
    es.grant_from_purchase(
        db,
        user_id="u2",
        platform="android",
        product_id=es.PARIS_PASS_7D,
        store_transaction_id="GPA.999",
    )
    es.activate(db, "u2")

    r = c.post("/api/v1/payment/rtdn?token=s3cret", json=_rtdn("GPA.999"))
    assert r.status_code == 204, r.text
    assert es.resolve_state(db, "u2")[0] == es.NOT_PURCHASED


def test_rtdn_ignores_unknown_notifications(client, monkeypatch):
    """订阅/测试通知等一律静默忽略并返 204 —— 返错误码会让 Pub/Sub 无限重投。"""
    c, _ = client
    monkeypatch.setattr(settings, "PLAY_RTDN_TOKEN", "s3cret")
    env = {"message": {"data": base64.b64encode(b'{"testNotification":{}}').decode()}}
    assert c.post("/api/v1/payment/rtdn?token=s3cret", json=env).status_code == 204
    assert c.post("/api/v1/payment/rtdn?token=s3cret", json={}).status_code == 204


# ── RTDN 鉴权改走 OIDC(密钥不再进 URL)─────────────────────────────────
#
# 老方案把共享密钥放在 `?token=`,而 URL 会原样写进 nginx/uvicorn 的 access log
# —— 这把"能伪造退款通知的钥匙"就此明文躺在日志与日志备份里,且永不轮换。
# Pub/Sub 推送发不了自定义 header,唯一能让密钥离开 URL 的办法是验它签的 OIDC 令牌。

_AUD = "https://api.gomuseum.app/api/v1/payment/rtdn"
_SA = "play-rtdn@gomuseum-499210.iam.gserviceaccount.com"


@pytest.fixture()
def oidc(monkeypatch):
    """配好 OIDC 并**关掉**老的共享密钥 —— 这样绿了才说明是 OIDC 自己在放行。"""
    monkeypatch.setattr(settings, "PLAY_RTDN_AUDIENCE", _AUD)
    monkeypatch.setattr(settings, "PLAY_RTDN_SERVICE_ACCOUNT_EMAIL", _SA)
    monkeypatch.setattr(settings, "PLAY_RTDN_TOKEN", None)

    def _claims(claims):
        import google.oauth2.id_token as gid

        monkeypatch.setattr(gid, "verify_oauth2_token", lambda *a, **k: claims)

    return _claims


def _good_claims(**over):
    return {"email": _SA, "email_verified": True, "aud": _AUD, **over}


def test_rtdn_oidc_accepts_and_revokes(client, oidc):
    """密钥完全不出现在 URL 里,照样能撤权益。"""
    c, db = client
    oidc(_good_claims())
    es.grant_from_purchase(
        db,
        user_id="u-oidc",
        platform="android",
        product_id=es.PARIS_PASS_7D,
        store_transaction_id="GPA.OIDC",
    )
    es.activate(db, "u-oidc")

    r = c.post(
        "/api/v1/payment/rtdn",
        json=_rtdn("GPA.OIDC"),
        headers={"Authorization": "Bearer signed.by.google"},
    )
    assert r.status_code == 204, r.text
    assert es.resolve_state(db, "u-oidc")[0] == es.NOT_PURCHASED


def test_rtdn_oidc_rejects_bad_signature(client, oidc, monkeypatch):
    c, _ = client
    import google.oauth2.id_token as gid

    def _boom(*a, **k):
        raise ValueError("Token signature invalid")

    monkeypatch.setattr(settings, "PLAY_RTDN_AUDIENCE", _AUD)
    monkeypatch.setattr(settings, "PLAY_RTDN_SERVICE_ACCOUNT_EMAIL", _SA)
    monkeypatch.setattr(settings, "PLAY_RTDN_TOKEN", None)
    monkeypatch.setattr(gid, "verify_oauth2_token", _boom)

    r = c.post(
        "/api/v1/payment/rtdn",
        json=_rtdn("X"),
        headers={"Authorization": "Bearer forged"},
    )
    assert r.status_code == 403


def test_rtdn_oidc_rejects_other_signers(client, oidc):
    """⭐ 验签+audience **还不够**。

    audience 只证明"这条是发给我们的",不证明"是我们授权的那个发信人发的"。
    少了签发者核对,任何能建 Pub/Sub 订阅指向我们的人都能伪造退款通知 ——
    而伪造退款 = 免费把别人的通票撤掉。
    """
    c, _ = client
    oidc(_good_claims(email="attacker@evil.example.com"))

    r = c.post(
        "/api/v1/payment/rtdn",
        json=_rtdn("X"),
        headers={"Authorization": "Bearer signed.but.wrong.sender"},
    )
    assert r.status_code == 403


def test_rtdn_oidc_rejects_unverified_email(client, oidc):
    c, _ = client
    oidc(_good_claims(email_verified=False))
    r = c.post(
        "/api/v1/payment/rtdn",
        json=_rtdn("X"),
        headers={"Authorization": "Bearer x"},
    )
    assert r.status_code == 403


@pytest.mark.parametrize(
    "aud,sa",
    [
        (_AUD, None),  # 配了 audience,忘了签发者
        (None, _SA),  # 配了签发者,忘了 audience ← 只有那道闸拦得住
    ],
    ids=["missing_sa_email", "missing_audience"],
)
def test_rtdn_half_configured_oidc_rejects(client, monkeypatch, aud, sa):
    """**半验必须当没验。** 两个配置项缺任一都拒收。

    第二组才是这条测试的要害:少了 audience,`verify_oauth2_token(aud=None)`
    **不再校验这条令牌是不是发给我们的**,而下游的签发者核对照样通过 ——
    于是同一个服务账号签给**任何别的服务**的令牌都能被拿来重放,伪造退款。
    (第一组会被签发者核对顺手拦下,单它一条证明不了这道闸有用 ——
     第一版就只写了它,把闸拿掉测试照样绿。)
    """
    c, _ = client
    import google.oauth2.id_token as gid

    monkeypatch.setattr(settings, "PLAY_RTDN_AUDIENCE", aud)
    monkeypatch.setattr(settings, "PLAY_RTDN_SERVICE_ACCOUNT_EMAIL", sa)
    monkeypatch.setattr(settings, "PLAY_RTDN_TOKEN", None)
    monkeypatch.setattr(gid, "verify_oauth2_token", lambda *a, **k: _good_claims())

    r = c.post(
        "/api/v1/payment/rtdn",
        json=_rtdn("X"),
        headers={"Authorization": "Bearer x"},
    )
    assert r.status_code == 403


def test_rtdn_nothing_configured_rejects_everything(client, monkeypatch):
    """两套都没配 = 公网上一个谁都能撤别人票的端点。必须拒绝一切。"""
    c, _ = client
    monkeypatch.setattr(settings, "PLAY_RTDN_TOKEN", None)
    monkeypatch.setattr(settings, "PLAY_RTDN_AUDIENCE", None)
    monkeypatch.setattr(settings, "PLAY_RTDN_SERVICE_ACCOUNT_EMAIL", None)

    assert c.post("/api/v1/payment/rtdn", json=_rtdn("X")).status_code == 403
    assert (
        c.post(
            "/api/v1/payment/rtdn",
            json=_rtdn("X"),
            headers={"Authorization": "Bearer whatever"},
        ).status_code
        == 403
    )


def test_rtdn_legacy_token_still_works_during_migration(client, monkeypatch):
    """⚠️ 过渡期必须两条路都通。

    切换顺序是「先部署代码 → 再改订阅 → 确认收得到 → 最后清空密钥」。
    若本次改动直接切断老路,这中间的退款通知会全被 403 拒收、
    Pub/Sub 重试若干天后丢弃 —— 又变回退款不撤权益的持续漏钱。
    """
    c, _ = client
    monkeypatch.setattr(settings, "PLAY_RTDN_TOKEN", "s3cret")
    monkeypatch.setattr(settings, "PLAY_RTDN_AUDIENCE", _AUD)
    monkeypatch.setattr(settings, "PLAY_RTDN_SERVICE_ACCOUNT_EMAIL", _SA)

    r = c.post("/api/v1/payment/rtdn?token=s3cret", json=_rtdn("nope"))
    assert r.status_code == 204


def test_log_event_never_rolls_back_business_data(client):
    """⭐ 埋点失败绝不能回滚调用方的业务数据。

    曾经在异常分支直接 db.rollback():埋点写失败 → 把调用方**尚未提交的**
    业务数据一起回滚。实测后果是游客登录刚建的 UserBenefits 被回滚,
    同设备第二次登录又建新账号 —— 防刷额度直接失效。
    """
    from app.services.event_log import log_event

    _, db = client
    # app_events 表在此 fixture 里不存在 → 写事件必然失败,正是要测的场景
    db.add(UserBenefits(user_id="biz-1", recognition_quota=5))
    log_event(db, "guest_created", device_id="d-x")
    db.commit()

    assert (
        db.query(UserBenefits).filter_by(user_id="biz-1").one_or_none() is not None
    ), "埋点失败把业务数据带走了"


def test_expired_pass_does_not_shadow_a_newly_bought_one(client):
    """⭐ 续购必须能激活(2026-07-29 外部评审发现,已复现)。

    到期只在读取时算,DB 里那行**永远停在 ACTIVE**。老票过期后用户续购,
    新票被那行过期的 ACTIVE 永久遮蔽 → resolve_state 恒为 expired、
    activate() 拒绝 —— 用户付了第二次钱,票永远激活不了。
    """
    from datetime import datetime, timedelta, timezone

    _, db = client
    db.add(
        Entitlement(
            user_id="renew",
            entitlement_type=es.PARIS_PASS_7D,
            scope="paris",
            status=es.ACTIVE,
            activated_at=datetime.now(timezone.utc) - timedelta(days=8),
            expires_at=datetime.now(timezone.utc) - timedelta(days=1),
        )
    )
    db.commit()
    assert es.resolve_state(db, "renew")[0] == es.EXPIRED

    es.grant_from_purchase(
        db,
        user_id="renew",
        platform="android",
        product_id=es.PARIS_PASS_7D,
        store_transaction_id="txn-renew",
    )
    assert es.resolve_state(db, "renew")[0] == es.PURCHASED_NOT_ACTIVATED
    state, _ = es.activate(db, "renew")
    assert state == es.ACTIVE, "续购的票必须能激活"


def test_receipt_owned_by_another_account_fails_loudly(client):
    """收据被别人先用过 → 必须显式失败,绝不静默返回成功。

    B 抢先用 A 的 purchase token 上报 → 权益归 B;A 再上报时命中幂等,
    若接口仍回 verified=true,A 付了钱、权益在 B 手上,还以为买成功了。
    """
    _, db = client
    es.grant_from_purchase(
        db,
        user_id="userB",
        platform="android",
        product_id=es.PARIS_PASS_7D,
        store_transaction_id="txn-shared",
    )
    with pytest.raises(es.PurchaseOwnershipConflict):
        es.grant_from_purchase(
            db,
            user_id="userA",
            platform="android",
            product_id=es.PARIS_PASS_7D,
            store_transaction_id="txn-shared",
        )
    assert es.resolve_state(db, "userA")[0] == es.NOT_PURCHASED


def test_unknown_product_is_rejected_not_silently_ignored(client, monkeypatch):
    """未知商品 → 400 显式拒绝。

    老商品(recognition_pack_10 / day_pass / premium_annual)已随收费定案下线。
    此前它们走另一条路:只写 user_benefits、不发 entitlement —— 而音频闸门只认
    entitlements,于是"付了钱却过不了闸"。下线后必须**显式拒绝**,不能再返回
    benefits_applied=False 的假成功(客户端会以为买到了东西)。
    """
    from app.api.v1.endpoints import payment as pay
    from app.api.v1.endpoints.payment import get_iap_verification_service

    c, db = client
    u = User(email="legacy@test.com", is_guest=False)
    db.add(u)
    db.commit()

    monkeypatch.setattr(
        pay.AuthService, "get_current_user", staticmethod(lambda *a, **k: u)
    )

    class _FakeIAP:
        async def verify_google_receipt(self, *a, **k):
            # 收据本身有效 —— 要测的是**它之后**那一步:商品不认识
            return {
                "valid": True,
                "product_id": "premium_annual",
                "transaction_id": "t1",
            }

    app.dependency_overrides[get_iap_verification_service] = lambda: _FakeIAP()
    try:
        r = c.post(
            "/api/v1/payment/verify",
            json={
                "platform": "android",
                "product_id": "premium_annual",
                "receipt_data": "whatever",
            },
            headers={"Authorization": "Bearer x"},
        )
    finally:
        app.dependency_overrides.pop(get_iap_verification_service, None)

    assert r.status_code == 400, r.text
    assert r.json()["detail"]["reason"] == "unknown_product"
    assert db.query(Entitlement).count() == 0, "未知商品绝不能发出权益"


def test_ownership_conflict_surfaces_as_409_not_500(client, monkeypatch):
    """收据归属冲突必须以 **409** 到达客户端,不能被吞成 500。

    I18 要求"幂等命中 ≠ 购买成功,归属不同必须显式失败"。但 HTTPException 也是
    Exception —— 端点里的通配 `except Exception` 会把它连同 502/400 一起转成
    500,前端根本区分不了"收据被别人用了"和"服务器炸了"。
    """
    from app.api.v1.endpoints import payment as pay
    from app.api.v1.endpoints.payment import get_iap_verification_service

    c, db = client
    u = User(email="a@test.com", is_guest=False)
    db.add(u)
    db.commit()
    # 这张收据已经归属别的账号
    es.grant_from_purchase(
        db,
        user_id="someone-else",
        platform="android",
        product_id=es.PARIS_PASS_7D,
        store_transaction_id="txn-taken",
    )

    monkeypatch.setattr(
        pay.AuthService, "get_current_user", staticmethod(lambda *a, **k: u)
    )

    class _FakeIAP:
        async def verify_google_receipt(self, *a, **k):
            return {
                "valid": True,
                "product_id": es.PARIS_PASS_7D,
                "transaction_id": "txn-taken",
            }

    app.dependency_overrides[get_iap_verification_service] = lambda: _FakeIAP()
    try:
        r = c.post(
            "/api/v1/payment/verify",
            json={
                "platform": "android",
                "product_id": es.PARIS_PASS_7D,
                "receipt_data": "whatever",
            },
            headers={"Authorization": "Bearer x"},
        )
    finally:
        app.dependency_overrides.pop(get_iap_verification_service, None)

    assert r.status_code == 409, r.text
    assert r.json()["detail"]["reason"] == "purchase_belongs_to_another_account"
