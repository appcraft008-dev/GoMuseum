"""
IAP Verification Service
Handles Apple App Store and Google Play Store receipt verification
"""

import json
import logging
from typing import Dict, Optional

import httpx

from app.core.config import settings
from app.core.exceptions import ServiceException

logger = logging.getLogger(__name__)


class IAPVerificationService:
    """Service for verifying in-app purchase receipts"""

    def __init__(self):
        """Initialize IAP verification service"""
        self.apple_verify_url_production = "https://buy.itunes.apple.com/verifyReceipt"
        self.apple_verify_url_sandbox = "https://sandbox.itunes.apple.com/verifyReceipt"
        self.google_package_name = getattr(
            settings, "GOOGLE_PACKAGE_NAME", "com.gomuseum.app"
        )
        logger.info("IAPVerificationService initialized")

    async def verify_apple_receipt(
        self, receipt_data: str, use_sandbox: bool = False
    ) -> Dict[str, any]:
        """
        Verify Apple App Store receipt

        Args:
            receipt_data: Base64 encoded receipt from iOS
            use_sandbox: Whether to use sandbox environment

        Returns:
            Dictionary containing verification result:
                - status: Verification status code
                - valid: Boolean indicating if receipt is valid
                - product_id: Product identifier
                - transaction_id: Unique transaction ID
                - purchase_date: Date of purchase
                - expires_date: Expiration date (for subscriptions)

        Raises:
            ServiceException: If verification fails
        """
        logger.info("Verifying Apple receipt")

        verify_url = (
            self.apple_verify_url_sandbox
            if use_sandbox
            else self.apple_verify_url_production
        )

        payload = {
            "receipt-data": receipt_data,
            "password": getattr(settings, "APPLE_SHARED_SECRET", ""),
            "exclude-old-transactions": True,
        }

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(verify_url, json=payload, timeout=30.0)

                result = response.json()
                status = result.get("status")

                # Status 21007 means sandbox receipt in production - retry with sandbox
                if status == 21007 and not use_sandbox:
                    logger.info("Sandbox receipt detected, retrying with sandbox URL")
                    return await self.verify_apple_receipt(
                        receipt_data, use_sandbox=True
                    )

                # Status 0 means valid
                if status == 0:
                    latest_receipt_info = result.get("latest_receipt_info", [])
                    if latest_receipt_info:
                        receipt = latest_receipt_info[0]
                        return {
                            "valid": True,
                            "status": status,
                            "product_id": receipt.get("product_id"),
                            "transaction_id": receipt.get("transaction_id"),
                            "purchase_date": receipt.get("purchase_date_ms"),
                            "expires_date": receipt.get("expires_date_ms"),
                            "is_subscription": "expires_date_ms" in receipt,
                            "platform": "ios",
                        }

                logger.warning(
                    f"Apple receipt verification failed with status {status}"
                )
                return {
                    "valid": False,
                    "status": status,
                    "error": self._get_apple_error_message(status),
                    "platform": "ios",
                }

        except httpx.TimeoutException:
            logger.error("Apple receipt verification timed out")
            raise ServiceException("Apple receipt verification timed out")
        except Exception as e:
            logger.error(f"Apple receipt verification error: {str(e)}")
            raise ServiceException(f"Apple receipt verification failed: {str(e)}")

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

    def _get_apple_error_message(self, status: int) -> str:
        """Get human-readable error message for Apple status code"""
        status_messages = {
            21000: "App Store could not read the JSON object",
            21002: "Receipt data property is malformed or missing",
            21003: "Receipt could not be authenticated",
            21004: "Shared secret does not match",
            21005: "Receipt server is not currently available",
            21006: "Receipt is valid but subscription has expired",
            21007: "Receipt is from sandbox but sent to production",
            21008: "Receipt is from production but sent to sandbox",
            21009: "Internal data access error",
            21010: "User account cannot be found or has been deleted",
        }

        return status_messages.get(status, f"Unknown status code: {status}")


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
