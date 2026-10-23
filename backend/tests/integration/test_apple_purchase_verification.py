"""iOS(App Store)购买校验与退款通知。spec 2026-10-22-ios-iap-verification-design。

没有 Apple 账号也能测全:现场生成一条「假根 → 中间 → 叶子」证书链(带 Apple 要求的
两个 OID),把假根当作信任根传给官方库,用叶子私钥签任意交易 JWS。
"""

import base64
import datetime
import time

import jwt
import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import NameOID
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
from app.services import iap_verification_service as ivs

BUNDLE = "com.gomuseum.app"
APP_ID = 1234567890
_LEAF_OID = "1.2.840.113635.100.6.11.1"
_INTERMEDIATE_OID = "1.2.840.113635.100.6.2.1"


def _cert(subject, issuer_name, pub, signing_key, *, ca, issuer_pub, oid=None):
    now = datetime.datetime.now(datetime.timezone.utc)
    b = (
        x509.CertificateBuilder()
        .subject_name(x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, subject)]))
        .issuer_name(x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, issuer_name)]))
        .public_key(pub)
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - datetime.timedelta(days=1))
        .not_valid_after(now + datetime.timedelta(days=30))
        .add_extension(x509.BasicConstraints(ca=ca, path_length=None), critical=True)
        .add_extension(
            x509.KeyUsage(
                digital_signature=not ca,
                content_commitment=False,
                key_encipherment=False,
                data_encipherment=False,
                key_agreement=False,
                key_cert_sign=ca,
                crl_sign=ca,
                encipher_only=False,
                decipher_only=False,
            ),
            critical=True,
        )
        .add_extension(x509.SubjectKeyIdentifier.from_public_key(pub), critical=False)
        .add_extension(
            x509.AuthorityKeyIdentifier.from_issuer_public_key(issuer_pub),
            critical=False,
        )
    )
    if oid:
        b = b.add_extension(
            x509.UnrecognizedExtension(x509.ObjectIdentifier(oid), b"\x05\x00"),
            critical=False,
        )
    return b.sign(signing_key, hashes.SHA256())


class FakeApple:
    """一套假的 Apple 签名设施。`root_der` 当信任根,`sign()` 出交易/通知 JWS。"""

    def __init__(self):
        root_k = ec.generate_private_key(ec.SECP256R1())
        mid_k = ec.generate_private_key(ec.SECP256R1())
        self.leaf_k = ec.generate_private_key(ec.SECP256R1())
        root = _cert(
            "Fake Root",
            "Fake Root",
            root_k.public_key(),
            root_k,
            ca=True,
            issuer_pub=root_k.public_key(),
        )
        mid = _cert(
            "Fake WWDR",
            "Fake Root",
            mid_k.public_key(),
            root_k,
            ca=True,
            issuer_pub=root_k.public_key(),
            oid=_INTERMEDIATE_OID,
        )
        leaf = _cert(
            "Fake Leaf",
            "Fake WWDR",
            self.leaf_k.public_key(),
            mid_k,
            ca=False,
            issuer_pub=mid_k.public_key(),
            oid=_LEAF_OID,
        )
        der = lambda c: c.public_bytes(serialization.Encoding.DER)  # noqa: E731
        self.root_der = der(root)
        self.x5c = [base64.b64encode(der(c)).decode() for c in (leaf, mid, root)]

    def sign(self, payload: dict, key=None) -> str:
        pem = (key or self.leaf_k).private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        )
        return jwt.encode(payload, pem, algorithm="ES256", headers={"x5c": self.x5c})

    def transaction(self, **over) -> str:
        p = {
            "transactionId": "2000000123456789",
            "originalTransactionId": "2000000123456789",
            "bundleId": BUNDLE,
            "productId": es.PARIS_PASS_7D,
            "type": "Consumable",
            "environment": "Production",
            "signedDate": int(time.time() * 1000),
            "purchaseDate": int(time.time() * 1000),
        }
        p.update(over)
        return self.sign(p)

    def notification(self, kind: str, txn_jws: str, env="Production") -> str:
        return self.sign(
            {
                "notificationType": kind,
                "notificationUUID": "00000000-0000-0000-0000-000000000001",
                "version": "2.0",
                "signedDate": int(time.time() * 1000),
                "data": {
                    "bundleId": BUNDLE,
                    "appAppleId": APP_ID,
                    "environment": env,
                    "signedTransactionInfo": txn_jws,
                },
            }
        )


@pytest.fixture()
def apple(monkeypatch):
    fake = FakeApple()
    monkeypatch.setattr(ivs, "_apple_root_certificates", lambda: [fake.root_der])
    monkeypatch.setattr(settings, "APPLE_BUNDLE_ID", BUNDLE, raising=False)
    monkeypatch.setattr(settings, "APPLE_APP_ID", APP_ID, raising=False)
    return fake


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


async def _verify(jws, product_id=es.PARIS_PASS_7D):
    return await ivs.IAPVerificationService().verify_apple_transaction(jws, product_id)


# ── 校验函数 ──────────────────────────────────────────────


@pytest.mark.asyncio
async def test_valid_production_transaction(apple):
    out = await _verify(apple.transaction())
    assert out["valid"] is True, out
    assert out["transaction_id"] == "2000000123456789"
    assert out["environment"] == "production"
    assert out["platform"] == "ios"


@pytest.mark.asyncio
async def test_valid_sandbox_transaction(apple):
    """审核员在 prod 后端上用 Sandbox 买(spec §4.3)—— 必须能过。"""
    out = await _verify(apple.transaction(environment="Sandbox"))
    assert out["valid"] is True, out
    assert out["environment"] == "sandbox"


@pytest.mark.asyncio
async def test_signed_by_untrusted_key_rejected(apple):
    """x5c 照抄真链、但用别的私钥签 → 验签失败。"""
    forged = apple.sign(
        {
            "transactionId": "999",
            "bundleId": BUNDLE,
            "productId": es.PARIS_PASS_7D,
            "type": "Consumable",
            "environment": "Production",
            "signedDate": int(time.time() * 1000),
        },
        key=ec.generate_private_key(ec.SECP256R1()),
    )
    out = await _verify(forged)
    assert out["valid"] is False
    assert out["error"] == "apple_jws_invalid"


@pytest.mark.asyncio
async def test_chain_not_rooted_at_trusted_root_rejected(apple, monkeypatch):
    other = FakeApple()
    monkeypatch.setattr(ivs, "_apple_root_certificates", lambda: [other.root_der])
    out = await _verify(apple.transaction())
    assert out["valid"] is False


@pytest.mark.asyncio
async def test_garbage_rejected(apple):
    out = await _verify("完全编造的凭证")
    assert out["valid"] is False
    assert out["error"] == "apple_jws_invalid"


@pytest.mark.asyncio
async def test_other_app_bundle_rejected(apple):
    out = await _verify(apple.transaction(bundleId="com.evil.app"))
    assert out["valid"] is False


@pytest.mark.asyncio
async def test_product_mismatch_rejected(apple):
    """A 商品的交易不能冒充 B 商品。"""
    out = await _verify(apple.transaction(productId="nl_pass_7d"))
    assert out["valid"] is False
    assert out["error"] == "apple_product_mismatch"


@pytest.mark.asyncio
async def test_non_consumable_rejected(apple):
    out = await _verify(apple.transaction(type="Non-Consumable"))
    assert out["valid"] is False
    assert out["error"] == "apple_not_consumable"


@pytest.mark.asyncio
async def test_revoked_transaction_rejected(apple):
    out = await _verify(apple.transaction(revocationDate=int(time.time() * 1000)))
    assert out["valid"] is False
    assert out["error"] == "apple_revoked"


@pytest.mark.asyncio
async def test_missing_app_id_rejects_production_but_not_sandbox(apple, monkeypatch):
    """失败关闭(I15):没配 APPLE_APP_ID 就无法确认 Production 交易属于我们 → 拒;
    Sandbox 不需要 App ID,账号开通前的联调不受阻。"""
    monkeypatch.setattr(settings, "APPLE_APP_ID", None, raising=False)
    assert (await _verify(apple.transaction()))["valid"] is False
    assert (await _verify(apple.transaction(environment="Sandbox")))["valid"] is True


@pytest.mark.asyncio
async def test_xcode_local_transaction_rejected(apple):
    """Xcode 本地 StoreKit 测试的交易不是 Apple 签的,绝不能进权益。"""
    assert (await _verify(apple.transaction(environment="Xcode")))["valid"] is False
    assert (await _verify(apple.transaction(environment="LocalTesting")))[
        "valid"
    ] is False


# ── /payment/verify 端到端 ────────────────────────────────


def _login(c, email="ios@gomuseum.app"):
    return c.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "username": email.split("@")[0],
            "password": "Passw0rd!1",
        },
    ).json()["access_token"]


def _post_verify(c, tok, jws, product_id=es.PARIS_PASS_7D):
    return c.post(
        "/api/v1/payment/verify",
        json={"platform": "ios", "receipt_data": jws, "product_id": product_id},
        headers={"Authorization": f"Bearer {tok}"},
    )


def test_ios_purchase_grants_pass(client, apple):
    c, db = client
    r = _post_verify(c, _login(c), apple.transaction())
    assert r.status_code == 200, r.text
    assert r.json()["verified"] is True
    p = db.query(Purchase).one()
    assert p.platform == "ios"
    assert p.store_transaction_id == "2000000123456789", "幂等键必须来自 Apple 签名(I9)"
    ent = db.query(Entitlement).one()
    assert ent.status == es.PURCHASED_NOT_ACTIVATED
    assert ent.granted_reason == "purchase"


def test_sandbox_purchase_is_marked(client, apple):
    """§4.3:Sandbox 票照发,但必须可区分。"""
    c, db = client
    r = _post_verify(c, _login(c), apple.transaction(environment="Sandbox"))
    assert r.json()["verified"] is True
    assert db.query(Entitlement).one().granted_reason == "sandbox"


def test_ios_resubmit_is_idempotent(client, apple):
    """SK2 重启后重投未 finish 的交易 → 同一笔不发第二张票。"""
    c, db = client
    tok = _login(c)
    jws = apple.transaction()
    assert _post_verify(c, tok, jws).json()["verified"] is True
    assert _post_verify(c, tok, jws).json()["verified"] is True
    assert db.query(Entitlement).count() == 1


def test_ios_transaction_of_another_account_is_409(client, apple):
    c, db = client
    jws = apple.transaction()
    assert _post_verify(c, _login(c, "a@x.app"), jws).json()["verified"] is True
    r = _post_verify(c, _login(c, "b@x.app"), jws)
    assert r.status_code == 409, r.text


def test_ios_bad_jws_grants_nothing(client, apple):
    c, db = client
    r = _post_verify(c, _login(c), "完全编造的凭证")
    assert r.json()["verified"] is False
    assert db.query(Entitlement).count() == 0


# ── 退款通知 ──────────────────────────────────────────────


def _notify(c, signed):
    return c.post("/api/v1/payment/apple-notifications", json={"signedPayload": signed})


def _granted(db, txn="2000000123456789", user="u-ios"):
    es.grant_from_purchase(
        db,
        user_id=user,
        platform="ios",
        product_id=es.PARIS_PASS_7D,
        store_transaction_id=txn,
    )
    es.activate(db, user)
    assert es.resolve_state(db, user)[0] == es.ACTIVE


@pytest.mark.parametrize("kind,status", [("REFUND", "refunded"), ("REVOKE", "revoked")])
def test_refund_notification_revokes(client, apple, kind, status):
    c, db = client
    _granted(db)
    r = _notify(c, apple.notification(kind, apple.transaction()))
    assert r.status_code == 200, r.text
    assert es.resolve_state(db, "u-ios")[0] == es.NOT_PURCHASED, "退款后不该还生效(I10)"
    assert db.query(Purchase).one().status == status


def test_sandbox_refund_notification_revokes(client, apple):
    c, db = client
    _granted(db)
    signed = apple.notification(
        "REFUND", apple.transaction(environment="Sandbox"), env="Sandbox"
    )
    assert _notify(c, signed).status_code == 200
    assert es.resolve_state(db, "u-ios")[0] == es.NOT_PURCHASED


def test_other_notification_types_change_nothing(client, apple):
    c, db = client
    _granted(db)
    for kind in ("CONSUMPTION_REQUEST", "REFUND_DECLINED", "TEST"):
        assert (
            _notify(c, apple.notification(kind, apple.transaction())).status_code == 200
        )
    assert es.resolve_state(db, "u-ios")[0] == es.ACTIVE


def test_forged_notification_is_403_and_changes_nothing(client, apple):
    c, db = client
    _granted(db)
    other = FakeApple()  # 不受信任的根签的
    r = _notify(c, other.notification("REFUND", other.transaction()))
    assert r.status_code == 403
    assert es.resolve_state(db, "u-ios")[0] == es.ACTIVE


def test_refund_for_unknown_transaction_is_harmless(client, apple):
    """重复推送/别家的交易:找不到订单,不报错(否则 Apple 会无限重投)。"""
    c, _ = client
    signed = apple.notification("REFUND", apple.transaction(transactionId="nope"))
    assert _notify(c, signed).status_code == 200
