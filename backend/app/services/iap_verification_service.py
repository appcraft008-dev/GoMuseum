"""
IAP Verification Service
Handles Apple App Store and Google Play Store receipt verification
"""

import json
import logging
from pathlib import Path
from typing import Dict, Optional

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)


class IAPVerificationService:
    """Service for verifying in-app purchase receipts"""

    def __init__(self):
        """Initialize IAP verification service"""
        self.google_package_name = getattr(
            settings, "GOOGLE_PACKAGE_NAME", "com.gomuseum.app"
        )
        logger.info("IAPVerificationService initialized")

    # ── App Store(StoreKit 2)──────────────────────────────────────────────
    #
    # 客户端(in_app_purchase_storekit,SK2 默认开)交来的 `receipt_data` 是 Apple
    # 签名的**交易 JWS**,不是旧式 app receipt。此前这里调的是已弃用的 verifyReceipt、
    # 按订阅读 latest_receipt_info —— 从无客户端调用过,喂 JWS 必然失败。
    #
    # 验签全交给 Apple 官方库(x5c 链验到 Apple Root CA G3 + ES256):手写证书链验证
    # 写错 = 任何人能伪造通票。离线验,不需要 .p8。
    # spec: docs/superpowers/specs/2026-10-22-ios-iap-verification-design.md

    def _apple_verifiers(self) -> list:
        """先 Production 后 Sandbox。审核员在 prod 后端上用 Sandbox 买(spec §4.3)。

        Production 必须有 APPLE_APP_ID:没有就无法确认交易属于我们 → 不建,
        Production 交易一律被 Sandbox verifier 以环境不符拒掉(失败关闭,I15)。
        """
        from appstoreserverlibrary.models.Environment import Environment
        from appstoreserverlibrary.signed_data_verifier import SignedDataVerifier

        roots = _apple_root_certificates()
        bundle = settings.APPLE_BUNDLE_ID
        out = []
        if settings.APPLE_APP_ID:
            out.append(
                SignedDataVerifier(
                    roots,
                    False,
                    Environment.PRODUCTION,
                    bundle,
                    int(settings.APPLE_APP_ID),
                )
            )
        out.append(SignedDataVerifier(roots, False, Environment.SANDBOX, bundle))
        return out

    def _apple_decode(self, method: str, signed: str):
        """依次用各环境验;返回 (解码结果, 验过的 verifier),都不过抛最后一个异常。
        每个 verifier 各自完整验签名/证书/App/环境,换环境重试不会放宽任何一项。"""
        from appstoreserverlibrary.signed_data_verifier import VerificationException

        last = None
        for v in self._apple_verifiers():
            try:
                return getattr(v, method)(signed), v
            except VerificationException as e:
                last = e
        raise last

    async def verify_apple_transaction(self, jws: str, product_id: str) -> Dict:
        """校验 SK2 交易 JWS。返回形状与 verify_google_receipt 一致,下游不分平台。

        `transaction_id` 取自 Apple 签名内的 transactionId(I9)。
        `environment` 供 payment.py 给 Sandbox 票打标(spec §4.3)。
        """
        from appstoreserverlibrary.signed_data_verifier import VerificationException

        def fail(error: str) -> Dict:
            logger.warning("Apple transaction rejected: %s", error)
            return {"valid": False, "platform": "ios", "error": error}

        try:
            t, _ = self._apple_decode("verify_and_decode_signed_transaction", jws)
        except VerificationException:
            return fail("apple_jws_invalid")
        if t.productId != product_id:
            # 否则 A 商品的交易能冒充 B 商品
            return fail("apple_product_mismatch")
        if t.rawType != "Consumable":
            return fail("apple_not_consumable")
        if t.revocationDate is not None:
            return fail("apple_revoked")
        if not t.transactionId:
            return fail("apple_transaction_id_missing")
        return {
            "valid": True,
            "platform": "ios",
            "product_id": t.productId,
            "transaction_id": t.transactionId,
            "environment": t.rawEnvironment.lower(),
        }

    def parse_apple_notification(self, signed_payload: str):
        """App Store Server Notifications V2 → (reason, transaction_id) 或 (None, None)。

        只处理 REFUND / REVOKE;其余类型(CONSUMPTION_REQUEST 等)返回 (None, None)。
        验签不过抛 VerificationException(端点据此回 403)。内层交易用验过外层的
        同一个 verifier 验 —— 环境必须一致。
        """
        n, v = self._apple_decode("verify_and_decode_notification", signed_payload)
        reason = {"REFUND": "refunded", "REVOKE": "revoked"}.get(n.rawNotificationType)
        if not reason or not n.data or not n.data.signedTransactionInfo:
            return None, None
        t = v.verify_and_decode_signed_transaction(n.data.signedTransactionInfo)
        return reason, t.transactionId

    _PLAY_API = "https://androidpublisher.googleapis.com/androidpublisher/v3"

    def _play_access_token(self) -> Optional[str]:
        """用服务账号换 androidpublisher 访问令牌。未配置返回 None(调用方拒绝)。"""
        raw = getattr(settings, "GOOGLE_PLAY_SERVICE_ACCOUNT", None)
        if not raw:
            return None
        try:
            import json as _json

            from google.auth.transport.requests import Request as _GRequest
            from google.oauth2 import service_account

            info = (
                _json.loads(raw)
                if raw.lstrip().startswith("{")
                else _json.load(open(raw))
            )
            creds = service_account.Credentials.from_service_account_info(
                info, scopes=["https://www.googleapis.com/auth/androidpublisher"]
            )
            creds.refresh(_GRequest())
            return creds.token
        except Exception:
            logger.exception("Play service account credential load failed")
            return None

    async def acknowledge_google_purchase(
        self, purchase_token: str, product_id: str
    ) -> bool:
        """向 Play 确认已交付。**不做的话 Google 会在 3 天后自动全额退款** ——
        每一笔收入都会悄悄退掉,而我们这边看起来一切正常。

        幂等:已确认的再调返回 400,视为成功。
        """
        token = self._play_access_token()
        if not token:
            return False
        url = (
            f"{self._PLAY_API}/applications/{self.google_package_name}"
            f"/purchases/products/{product_id}/tokens/{purchase_token}:acknowledge"
        )
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                r = await client.post(
                    url, headers={"Authorization": f"Bearer {token}"}, json={}
                )
        except Exception as e:
            logger.error("Play acknowledge request failed: %s", e)
            return False
        if r.status_code in (200, 204):
            return True
        if r.status_code == 400 and "already been acknowledged" in r.text:
            return True  # 幂等
        logger.error("Play acknowledge failed %s: %s", r.status_code, r.text[:200])
        return False

    async def verify_google_receipt(
        self, purchase_token: str, product_id: str, subscription: bool = False
    ) -> Dict[str, any]:
        """校验 Google Play 购买凭证(Play Developer API v3)。

        ⚠️ **失败一律关闭**。此前这里是 mock:对任何 purchase_token 都返回
        valid=True,任何登录用户 POST 一个编造的 receipt_data 就能白拿通票;
        且不返回 transaction_id,导致幂等键回落成攻击者可控的字符串 → 无限刷票。

        返回 `transaction_id` = Play 的 **orderId**(稳定、唯一),权益幂等靠它。
        """
        logger.info("Verifying Google receipt for product: %s", product_id)

        token = self._play_access_token()
        if not token:
            # 没有凭证 = 无法证明这笔购买真实存在 → 拒绝,绝不放行
            return {
                "valid": False,
                "platform": "android",
                "error": "google_play_not_configured",
            }

        kind = "subscriptions" if subscription else "products"
        id_seg = "subscriptionId" if subscription else "productId"
        url = (
            f"{self._PLAY_API}/applications/{self.google_package_name}"
            f"/purchases/{kind}/{product_id}/tokens/{purchase_token}"
        )
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                r = await client.get(url, headers={"Authorization": f"Bearer {token}"})
        except Exception as e:
            logger.error("Play API request failed: %s", e)
            return {"valid": False, "platform": "android", "error": "play_api_error"}

        if r.status_code != 200:
            # 404 = 该 token 不存在(伪造/已消费);其余按失败处理
            logger.warning(
                "Play API %s for %s: %s", r.status_code, id_seg, r.text[:200]
            )
            return {
                "valid": False,
                "platform": "android",
                "error": f"play_api_{r.status_code}",
            }

        data = r.json()
        # purchaseState: 0=Purchased 1=Canceled 2=Pending —— 只有 0 才发权益
        state = data.get("purchaseState")
        order_id = data.get("orderId")
        return {
            "valid": state == 0 and bool(order_id),
            "status": state,
            "product_id": product_id,
            "transaction_id": order_id,
            "purchase_token": purchase_token,
            "purchase_state": state,
            "is_subscription": subscription,
            "platform": "android",
            "acknowledged": data.get("acknowledgementState"),
        }


_APPLE_ROOT_CERT = (
    Path(__file__).resolve().parent.parent / "certs" / "AppleRootCA-G3.cer"
)


def _apple_root_certificates() -> list[bytes]:
    """Apple Root CA - G3(公开证书,apple.com/certificateauthority;
    SHA-256 63:34:3A:BF:…:91:79)。测试里替换成假根。"""
    return [_APPLE_ROOT_CERT.read_bytes()]


# Singleton instance
_iap_verification_service_instance = None


def get_iap_verification_service() -> IAPVerificationService:
    """
    Get or create IAPVerificationService singleton instance

    Returns:
        IAPVerificationService instance
    """
    global _iap_verification_service_instance
    if _iap_verification_service_instance is None:
        _iap_verification_service_instance = IAPVerificationService()
    return _iap_verification_service_instance
