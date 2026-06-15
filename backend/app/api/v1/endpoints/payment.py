"""
Payment API Endpoints
Handles IAP verification and user benefits management
"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.exceptions import ServiceException
from app.services.auth_service import AuthService
from app.services.benefits_service import get_benefits_service
from app.services.iap_verification_service import get_iap_verification_service

logger = logging.getLogger(__name__)

router = APIRouter()
security = HTTPBearer()


# Request/Response Models
class VerifyReceiptRequest(BaseModel):
    """Request model for receipt verification"""

    platform: str = Field(..., description="Platform: ios or android")
    receipt_data: str = Field(..., description="Receipt data or purchase token")
    product_id: str = Field(..., description="Product identifier")
    user_id: Optional[str] = Field(None, description="User ID (if authenticated)")
    device_id: Optional[str] = Field(
        None, description="Device ID (for anonymous users)"
    )


class VerifyReceiptResponse(BaseModel):
    """Response model for receipt verification"""

    verified: bool
    product_id: str
    transaction_id: Optional[str]
    benefits_applied: bool
    message: str


class BenefitsResponse(BaseModel):
    """Response model for user benefits"""

    has_access: bool
    recognition_quota: int
    referral_bonus_quota: int
    total_quota: int
    is_premium: bool
    day_pass_active: bool
    total_used: int
    premium_expires_at: Optional[str]
    day_pass_expires_at: Optional[str]


@router.post("/verify", response_model=VerifyReceiptResponse)
async def verify_purchase(
    request: VerifyReceiptRequest,
    db: Session = Depends(get_db),
    iap_service=Depends(get_iap_verification_service),
    benefits_service=Depends(lambda db=Depends(get_db): get_benefits_service(db)),
) -> VerifyReceiptResponse:
    """
    Verify in-app purchase receipt and apply benefits

    Args:
        request: Receipt verification request
        db: Database session (injected)
        iap_service: IAP verification service (injected)
        benefits_service: Benefits service (injected)

    Returns:
        Verification result and benefits status

    Example:
        ```bash
        curl -X POST "http://localhost:8000/api/v1/payment/verify" \\
             -H "Content-Type: application/json" \\
             -d '{
                   "platform": "ios",
                   "receipt_data": "base64_encoded_receipt",
                   "product_id": "com.gomuseum.recognition_pack_10",
                   "device_id": "device_12345"
                 }'
        ```
    """
    logger.info(
        f"Verifying {request.platform} purchase for product: {request.product_id}"
    )

    try:
        # Verify receipt based on platform
        if request.platform == "ios":
            verification = await iap_service.verify_apple_receipt(request.receipt_data)
        elif request.platform == "android":
            is_subscription = "annual" in request.product_id.lower()
            verification = await iap_service.verify_google_receipt(
                purchase_token=request.receipt_data,
                product_id=request.product_id,
                subscription=is_subscription,
            )
        else:
            raise HTTPException(
                status_code=400,
                detail={
                    "error": "InvalidPlatform",
                    "detail": f"Platform must be 'ios' or 'android'",
                },
            )

        if not verification.get("valid"):
            logger.warning(f"Receipt verification failed: {verification.get('error')}")
            return VerifyReceiptResponse(
                verified=False,
                product_id=request.product_id,
                transaction_id=None,
                benefits_applied=False,
                message=verification.get("error", "Receipt verification failed"),
            )

        # Apply benefits based on product ID
        benefits_applied = _apply_benefits(
            product_id=request.product_id,
            user_id=request.user_id,
            device_id=request.device_id,
            benefits_service=benefits_service,
        )

        logger.info(f"Purchase verified and benefits applied: {request.product_id}")

        return VerifyReceiptResponse(
            verified=True,
            product_id=verification["product_id"],
            transaction_id=verification.get("transaction_id"),
            benefits_applied=benefits_applied,
            message="Purchase verified and benefits applied successfully",
        )

    except ServiceException as e:
        logger.error(f"Service error: {str(e)}")
        raise HTTPException(
            status_code=500, detail={"error": "ServiceError", "detail": str(e)}
        )
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500, detail={"error": "InternalServerError", "detail": str(e)}
        )


@router.get("/benefits", response_model=BenefitsResponse)
async def get_benefits(
    device_id: Optional[str] = None,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
) -> BenefitsResponse:
    """
    Get user benefits and quota information

    Args:
        user_id: User identifier (query parameter)
        device_id: Device identifier (query parameter)
        db: Database session (injected)

    Returns:
        Current benefits status

    Example:
        ```bash
        curl -X GET "http://localhost:8000/api/v1/payment/benefits?device_id=device_12345"
        ```
    """
    user = AuthService.get_current_user(db, credentials.credentials)
    user_id = str(user.id)
    logger.info(f"Getting benefits for user_id={user_id}, device_id={device_id}")

    try:
        benefits_service = get_benefits_service(db)
        benefits = benefits_service.check_access(user_id, device_id)

        return BenefitsResponse(**benefits)

    except ServiceException as e:
        logger.error(f"Service error: {str(e)}")
        raise HTTPException(
            status_code=500, detail={"error": "ServiceError", "detail": str(e)}
        )
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500, detail={"error": "InternalServerError", "detail": str(e)}
        )


@router.post("/consume")
async def consume_recognition(
    device_id: Optional[str] = None,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
):
    """
    Consume one recognition from user's quota (requires auth;
    user identity comes from the access token, not the query)

    Args:
        user_id: User identifier
        device_id: Device identifier
        db: Database session (injected)

    Returns:
        Success status and remaining quota

    Example:
        ```bash
        curl -X POST "http://localhost:8000/api/v1/payment/consume?device_id=device_12345"
        ```
    """
    user = AuthService.get_current_user(db, credentials.credentials)
    user_id = str(user.id)
    logger.info(f"Consuming recognition for user_id={user_id}, device_id={device_id}")

    try:
        benefits_service = get_benefits_service(db)
        success = benefits_service.consume_recognition(user_id, device_id)

        if not success:
            raise HTTPException(
                status_code=403,
                detail={
                    "error": "QuotaExceeded",
                    "detail": "No recognition quota available",
                },
            )

        # Get updated benefits
        benefits = benefits_service.check_access(user_id, device_id)

        return {
            "success": True,
            "message": "Recognition consumed successfully",
            "remaining_quota": benefits["total_quota"],
        }

    except HTTPException:
        raise
    except ServiceException as e:
        logger.error(f"Service error: {str(e)}")
        raise HTTPException(
            status_code=500, detail={"error": "ServiceError", "detail": str(e)}
        )
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500, detail={"error": "InternalServerError", "detail": str(e)}
        )


def _apply_benefits(
    product_id: str, user_id: Optional[str], device_id: Optional[str], benefits_service
) -> bool:
    """
    Apply benefits based on purchased product

    Args:
        product_id: Product identifier
        user_id: User identifier
        device_id: Device identifier
        benefits_service: Benefits service instance

    Returns:
        True if benefits applied successfully
    """
    try:
        # Recognition pack (10 recognitions)
        if "recognition_pack_10" in product_id:
            benefits_service.add_recognition_pack(user_id, device_id, quantity=10)
            return True

        # Day pass (24 hours unlimited)
        elif "day_pass" in product_id:
            benefits_service.activate_day_pass(user_id, device_id)
            return True

        # Premium annual subscription
        elif "premium_annual" in product_id:
            benefits_service.activate_premium(user_id, device_id, duration_days=365)
            return True

        else:
            logger.warning(f"Unknown product ID: {product_id}")
            return False

    except Exception as e:
        logger.error(f"Failed to apply benefits: {str(e)}")
        return False
