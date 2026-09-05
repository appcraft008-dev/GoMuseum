"""
Payment API Endpoints
Handles IAP verification and user benefits management
"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.core.exceptions import ServiceException
from app.core.rate_limit import limiter
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

    # ⚠️ 通票/会员状态**不在这里**:权益真相源是 entitlements(见 /entitlements 的
    # `can`)。此处只报免费层的额度账。曾经的 is_premium / day_pass_active 已随
    # 老商品下线一并移除 —— 它们早就不决定任何事,却还在广播(I13)。
    has_access: bool
    recognition_quota: int
    referral_bonus_quota: int
    total_quota: int
    total_used: int


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
            #
            # 但失败**不一定**意味着会退款:消耗型商品被客户端 consume 掉之后
            # 就已隐含确认,这里再 acknowledge 会得到 400 "not in a valid state"。
            # 那是正常路径,不是事故 —— 老客户端(autoConsume 默认 true)每笔都会
            # 走到这里。所以降为 warning,别用 error 淹没真正的告警。
            if request.platform == "android":
                ack = await iap_service.acknowledge_google_purchase(
                    purchase_token=request.receipt_data,
                    product_id=request.product_id,
                )
                if not ack:
                    logger.warning(
                        "acknowledge 未成功(若该笔已被客户端 consume 则属正常,"
                        "consume 隐含确认);否则 3 天后会被 Google 自动退款: %s",
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

        # 走到这里 = 不是商品目录里的通票。老商品(recognition_pack_10 / day_pass /
        # premium_annual)已随收费定案下线:APK 从未正式发布过,不存在会买它们的
        # 老客户端,留着只会长出"写了 user_benefits 却没有 entitlement"的账号 ——
        # 那种账号付了钱却过不了音频闸门(闸门只认 entitlements)。
        # 未知商品**显式拒绝**,不再返回 benefits_applied=False 的假成功。
        logger.warning("未知商品,拒绝: %s", request.product_id)
        raise HTTPException(
            status_code=400,
            detail={"reason": "unknown_product", "product_id": request.product_id},
        )

    # ⚠️ 必须放在通配 except 之前:HTTPException 也是 Exception,不透传的话
    # 本函数里所有精心选好的状态码都会被下面那条吞成 500 —— 包括 I18 要求的
    # 409(收据属于别的账号)和 502(商店没给交易 ID)。
    # 前端拿到 500 无法区分"收据被别人用了"和"服务器炸了"。
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

    except HTTPException:  # 同上:别把有意义的状态码吞成 500
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


class RtdnEnvelope(BaseModel):
    """Google Pub/Sub 推送信封(RTDN)。message.data 是 base64 的 JSON。"""

    message: dict = Field(default_factory=dict)
    subscription: Optional[str] = None


def verify_rtdn_oidc(authorization: Optional[str]) -> bool:
    """校验 Pub/Sub 随推送签发的 OIDC 令牌(`Authorization: Bearer <JWT>`)。

    验三件事,缺一不可:
      1. **签名**是 Google 的(`verify_oauth2_token` 拉 Google 公钥验签)
      2. `aud` == 我们建订阅时填的 audience —— 否则**任何一个 Google 账号**签发的
         合法 ID 令牌都能进来(签名是真的,但不是发给我们的)
      3. `email` == 我们指定的那个服务账号 —— audience 只证明"发给我们",
         这一条才证明"由我们授权的那个发信人发出"

    两个配置项缺任何一个都返回 False:**宁可拒收也不能半验**。
    """
    if not authorization or not authorization.lower().startswith("bearer "):
        return False
    audience = getattr(settings, "PLAY_RTDN_AUDIENCE", None)
    sa_email = getattr(settings, "PLAY_RTDN_SERVICE_ACCOUNT_EMAIL", None)
    if not audience or not sa_email:
        return False

    from google.auth.transport import requests as google_requests
    from google.oauth2 import id_token

    try:
        claims = id_token.verify_oauth2_token(
            authorization.split(" ", 1)[1].strip(),
            google_requests.Request(),
            audience,
        )
    except Exception as e:
        logger.warning("RTDN OIDC 校验失败: %s", e)
        return False

    if claims.get("email") != sa_email or not claims.get("email_verified"):
        logger.warning("RTDN OIDC 签发者不符: %s", claims.get("email"))
        return False
    return True


@router.post("/rtdn", status_code=204)
@limiter.limit("120/minute")
async def play_rtdn(
    request: Request,
    payload: RtdnEnvelope,
    token: Optional[str] = None,
    db: Session = Depends(get_db),
) -> None:
    """Google Play 实时开发者通知(退款/撤销)。

    ⚠️ **退款必须撤权益**:只标订单退款、留着 entitlement 生效 = 退了钱还能用满 7 天。

    ## 鉴权

    首选 **OIDC**:Pub/Sub 用指定服务账号给每条推送现签一个 JWT,放在
    `Authorization: Bearer`。密钥不进 URL、每条现签、几分钟过期。

    过渡期仍接受老的 `?token=<共享密钥>`,**仅当 PLAY_RTDN_TOKEN 还配着**。
    那个方案的问题不是强度,是**位置**:URL 会原样写进 nginx/uvicorn 的 access log,
    这把能伪造退款通知的钥匙就此明文躺在日志与日志备份里,而且永不轮换。
    切换完成后清空该变量,这条路自动关闭(见 config.py 里的切换顺序)。

    ⚠️ 限流是必需的,不是保守:本端点公开且未认证,而校验 OIDC 要向 Google 拉公钥
    —— 没有闸的话,一串伪造 Bearer 就能把我们放大成对 googleapis 的请求源,
    还会占满线程池。Pub/Sub 真实量远低于此;被限流的消息会重投,不会丢。

    幂等:revoke_for_purchase 找不到订单返 False,重复推送无副作用。
    鉴权通过后始终返 204 —— 返错误码会让 Pub/Sub 无限重投。
    """
    import base64
    import json as _json

    from fastapi.concurrency import run_in_threadpool

    # OIDC 校验是同步的、且会向 Google 发 HTTP。直接在协程里调 = 那段时间整个
    # 事件循环停摆(googleapis 一卡,全 API 跟着卡)。丢进线程池。
    authorized = await run_in_threadpool(
        verify_rtdn_oidc, request.headers.get("authorization")
    )
    if not authorized:
        expected = getattr(settings, "PLAY_RTDN_TOKEN", None)
        if not expected or token != expected:
            raise HTTPException(status_code=403, detail={"reason": "bad_rtdn_token"})
        # 还在走老路 —— 每收一条就提醒一次,免得"迁移完了"变成一句没人核对的口号
        logger.warning(
            "RTDN 仍在用 URL 共享密钥(?token=)。改用 OIDC 后请清空 "
            "PLAY_RTDN_TOKEN 并轮换旧密钥 —— 它已经明文进过 access log。"
        )

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
