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

from app.core.config import settings
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
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
    iap_service=Depends(get_iap_verification_service),
    benefits_service=Depends(lambda db=Depends(get_db): get_benefits_service(db)),
) -> VerifyReceiptResponse:
    """
    Verify in-app purchase receipt and apply benefits

    ⚠️ user_id **只认令牌**,不认请求体。曾用 `request.user_id or request.device_id`,
    而前端传 user_id=null → 回落成 device_id → 权益的 user_id 存成设备号字符串,
    可 /entitlements/me 是按令牌里的 UUID 查的,两者永不相等:
    **用户付了钱,通票落库了,自己却看不到**。同类错误此前也出现在 /entitlements/me
    (user_id 当查询参数)。请求体里的 user_id 字段保留只为兼容老客户端,不再采信。

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
    _user = AuthService.get_current_user(db, credentials.credentials)
    if _user.is_guest:
        # 买票前必须登录:通票挂 user_id,而游客身份是**设备绑定**的——
        # 游客买了票,换手机/清数据就永久拿不回(收据已消耗,恢复购买命中幂等、
        # 不给新用户发权益)。前端会先引导登录;这里是执行点,不能只靠 UI 拦。
        raise HTTPException(
            status_code=403, detail={"reason": "login_required_to_purchase"}
        )
    auth_user_id = str(_user.id)
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

        # 巴黎通票:落订单 + 发权益(purchased_not_activated,不开始计时)。
        # 幂等靠 store_transaction_id —— 恢复购买重复上报同一 token 不会发第二张。
        # 老商品(recognition_pack/day_pass)仍走下面的 _apply_benefits,老 APK 不破。
        from app.services import entitlement_service as _es

        # ⚠️ 别用等值判断:第二个 SKU(1日票/其他城市/多国票)会掉进下面的
        # 老商品分支,行为错乱。查商品目录 PASSES。
        if _es.is_pass_product(request.product_id):
            # ⚠️ 幂等键必须来自**商店**(Play 的 orderId),绝不回退到 receipt_data:
            # 那是客户端提供的字符串,攻击者改一个字符就能再拿一张票。
            txn = verification.get("transaction_id")
            if not txn:
                raise HTTPException(
                    status_code=502,
                    detail={"reason": "store_transaction_id_missing"},
                )
            try:
                _es.grant_from_purchase(
                    db,
                    user_id=auth_user_id,
                    platform=request.platform,
                    product_id=request.product_id,
                    store_transaction_id=txn,
                    receipt_payload=request.receipt_data,
                )
            except _es.PurchaseOwnershipConflict:
                # 这张收据已归属别的账号:回明确错误,不能假装成功
                raise HTTPException(
                    status_code=409,
                    detail={"reason": "purchase_belongs_to_another_account"},
                )
            # ⚠️ 必须向 Play 确认交付,否则 **3 天后自动全额退款** ——
            # 每笔收入都会悄悄退掉,而我们这边看起来一切正常。
            if request.platform == "android":
                ack = await iap_service.acknowledge_google_purchase(
                    purchase_token=request.receipt_data,
                    product_id=request.product_id,
                )
                if not ack:
                    logger.error(
                        "acknowledge 失败,该笔购买将在 3 天后被 Google 自动退款: %s",
                        txn,
                    )

            from app.services.event_log import log_event

            log_event(
                db,
                "purchase_succeeded",
                user_id=auth_user_id,
                device_id=request.device_id,
                product_id=request.product_id,
            )
            return VerifyReceiptResponse(
                verified=True,
                product_id=request.product_id,
                transaction_id=verification.get("transaction_id"),
                benefits_applied=True,
                message="Pass granted (not activated until first premium use)",
            )

        # Apply benefits based on product ID
        benefits_applied = _apply_benefits(
            product_id=request.product_id,
            user_id=auth_user_id,
            device_id=request.device_id,
            benefits_service=benefits_service,
        )

        # ⭐ 老商品只写 user_benefits,而**音频闸门只认 entitlements** ——
        # 不补这一张,用老 APK 买了 premium_annual/day_pass 的用户付了钱却听不了
        # 音频。真相源统一到 entitlements 之后,老路径必须自己把权益送过来。
        if benefits_applied:
            _b = benefits_service.get_or_create_benefits(
                auth_user_id, request.device_id
            )
            for _kind, _exp in (
                (_es.LEGACY_PREMIUM, _b.premium_expires_at if _b.is_premium else None),
                (
                    _es.LEGACY_DAY_PASS,
                    _b.day_pass_expires_at if _b.day_pass_active else None,
                ),
            ):
                if _exp is not None:
                    _es.grant_legacy_pass(
                        db, user_id=auth_user_id, kind=_kind, expires_at=_exp
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


class RtdnEnvelope(BaseModel):
    """Google Pub/Sub 推送信封(RTDN)。message.data 是 base64 的 JSON。"""

    message: dict = Field(default_factory=dict)
    subscription: Optional[str] = None


@router.post("/rtdn", status_code=204)
async def play_rtdn(
    payload: RtdnEnvelope,
    token: Optional[str] = None,
    db: Session = Depends(get_db),
) -> None:
    """Google Play 实时开发者通知(退款/撤销)。

    ⚠️ **退款必须撤权益**:只标订单退款、留着 entitlement 生效 = 退了钱还能用满 7 天。
    `revoke_for_purchase` 早就写好了,但此前**零调用方** —— 这里是它的入口。

    鉴权:Pub/Sub 推送 URL 上带 `?token=<共享密钥>`(在 Cloud Console 配置推送时写死)。
    这是 Google 官方推荐的最简方案;没配密钥则拒绝一切请求,不裸奔。

    幂等:revoke_for_purchase 找不到订单返 False,重复推送无副作用。
    始终返 204 —— 返错误码会让 Pub/Sub 无限重投。
    """
    import base64
    import json as _json

    expected = getattr(settings, "PLAY_RTDN_TOKEN", None)
    if not expected or token != expected:
        raise HTTPException(status_code=403, detail={"reason": "bad_rtdn_token"})

    try:
        raw = payload.message.get("data") or ""
        body = _json.loads(base64.b64decode(raw).decode("utf-8")) if raw else {}
    except Exception:
        logger.warning("RTDN payload undecodable, ignoring")
        return

    voided = body.get("voidedPurchaseNotification")
    if not voided:
        # 订阅/测试通知等:当前只处理退款,其余静默忽略(不重投)
        return

    from app.services import entitlement_service as _es
    from app.services.event_log import log_event

    order_id = voided.get("orderId")
    if not order_id:
        return
    revoked = _es.revoke_for_purchase(db, order_id, reason="refunded")
    log_event(db, "purchase_refunded", product_id=order_id, revoked=revoked)
    logger.info("RTDN voided purchase %s → revoked=%s", order_id, revoked)
