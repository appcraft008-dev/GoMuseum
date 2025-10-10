"""
IAP Verification Service
Handles Apple App Store and Google Play Store receipt verification
"""

import logging
import httpx
import json
from typing import Dict, Optional
from app.core.config import settings
from app.core.exceptions import ServiceException

logger = logging.getLogger(__name__)


class IAPVerificationService:
    """Service for verifying in-app purchase receipts"""

    def __init__(self):
        """Initialize IAP verification service"""
        self.apple_verify_url_production = "https://buy.itunes.apple.com/verifyReceipt"
        self.apple_verify_url_sandbox = "https://sandbox.itunes.apple.com/verifyReceipt"
        self.google_package_name = getattr(settings, "GOOGLE_PACKAGE_NAME", "com.gomuseum.app")
        logger.info("IAPVerificationService initialized")

    async def verify_apple_receipt(
        self,
        receipt_data: str,
        use_sandbox: bool = False
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
            self.apple_verify_url_sandbox if use_sandbox
            else self.apple_verify_url_production
        )

        payload = {
            "receipt-data": receipt_data,
            "password": getattr(settings, "APPLE_SHARED_SECRET", ""),
            "exclude-old-transactions": True
        }

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    verify_url,
                    json=payload,
                    timeout=30.0
                )

                result = response.json()
                status = result.get("status")

                # Status 21007 means sandbox receipt in production - retry with sandbox
                if status == 21007 and not use_sandbox:
                    logger.info("Sandbox receipt detected, retrying with sandbox URL")
                    return await self.verify_apple_receipt(receipt_data, use_sandbox=True)

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
                            "platform": "ios"
                        }

                logger.warning(f"Apple receipt verification failed with status {status}")
                return {
                    "valid": False,
                    "status": status,
                    "error": self._get_apple_error_message(status),
                    "platform": "ios"
                }

        except httpx.TimeoutException:
            logger.error("Apple receipt verification timed out")
            raise ServiceException("Apple receipt verification timed out")
        except Exception as e:
            logger.error(f"Apple receipt verification error: {str(e)}")
            raise ServiceException(f"Apple receipt verification failed: {str(e)}")

    async def verify_google_receipt(
        self,
        purchase_token: str,
        product_id: str,
        subscription: bool = False
    ) -> Dict[str, any]:
        """
        Verify Google Play Store receipt

        Args:
            purchase_token: Purchase token from Android
            product_id: Product identifier
            subscription: Whether this is a subscription purchase

        Returns:
            Dictionary containing verification result

        Raises:
            ServiceException: If verification fails

        Note:
            Requires Google Play Developer API credentials to be configured
        """
        logger.info(f"Verifying Google receipt for product: {product_id}")

        try:
            # This is a simplified version - in production, use Google Play Developer API
            # with proper OAuth2 authentication
            #
            # from google.oauth2 import service_account
            # from googleapiclient.discovery import build
            #
            # credentials = service_account.Credentials.from_service_account_file(
            #     'service_account.json',
            #     scopes=['https://www.googleapis.com/auth/androidpublisher']
            # )
            # service = build('androidpublisher', 'v3', credentials=credentials)
            #
            # if subscription:
            #     result = service.purchases().subscriptions().get(
            #         packageName=self.google_package_name,
            #         subscriptionId=product_id,
            #         token=purchase_token
            #     ).execute()
            # else:
            #     result = service.purchases().products().get(
            #         packageName=self.google_package_name,
            #         productId=product_id,
            #         token=purchase_token
            #     ).execute()

            # For MVP, return mock verification
            # TODO: Implement real Google Play verification
            logger.warning("Google Play verification not fully implemented - using mock")

            return {
                "valid": True,
                "status": 0,
                "product_id": product_id,
                "purchase_token": purchase_token,
                "purchase_state": 0,  # 0 = Purchased
                "is_subscription": subscription,
                "platform": "android",
                "mock": True  # Indicates this is mock verification
            }

        except Exception as e:
            logger.error(f"Google receipt verification error: {str(e)}")
            raise ServiceException(f"Google receipt verification failed: {str(e)}")

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
            21010: "User account cannot be found or has been deleted"
        }

        return status_messages.get(
            status,
            f"Unknown status code: {status}"
        )


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
