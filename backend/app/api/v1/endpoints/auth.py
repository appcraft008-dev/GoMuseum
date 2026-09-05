"""Authentication API endpoints"""

import html as _html
import logging
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, status
from fastapi.responses import HTMLResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.rate_limit import limiter
from app.models.user import User
from app.schemas.auth import (
    LoginRequest,
    OAuthRequest,
    RefreshTokenRequest,
    RegisterRequest,
    TokenResponse,
)
from app.schemas.user import UserResponse
from app.services import account_recovery, mailer
from app.services.auth_service import AuthService

logger = logging.getLogger(__name__)
# endpoints → v1 → api → app
_TEMPLATES = Path(__file__).resolve().parents[3] / "templates"

router = APIRouter(prefix="/auth", tags=["Authentication"])
security = HTTPBearer()
# 注册/Google 登录时游客令牌是**可选**的:带了就就地转正,没带才新建
_optional_bearer = HTTPBearer(auto_error=False)


@router.post(
    "/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED
)
@limiter.limit("5/minute")
def register(
    request: Request,
    payload: RegisterRequest,
    background: BackgroundTasks,
    credentials: HTTPAuthorizationCredentials | None = Depends(_optional_bearer),
    db: Session = Depends(get_db),
):
    """
    Register a new user with email and password

    - **email**: User's email address (must be unique)
    - **password**: User's password (min 8 characters recommended)
    - **username**: Optional display name

    Returns access token, refresh token, and user profile
    """
    resp = AuthService.register(db, payload, credentials)

    # 顺手发一封邮箱验证信。**放后台、且吞掉一切异常** —— 发信是锦上添花,
    # 注册是主线;SMTP 抽风绝不能让人注册不了。
    #
    # 为什么值得发:邮箱写错了(少个字母、填成同事的)在此刻毫无症状,
    # 直到某天他忘了密码 —— 那时才发现唯一的找回通道从一开始就是断的。
    user = db.query(User).filter(User.email == payload.email).one_or_none()
    if user is not None:
        background.add_task(
            _send_verification_quietly,
            db,
            user,
            str(request.base_url).rstrip("/"),
            request.headers.get("accept-language"),
        )
    return resp


def _send_verification_quietly(db, user, base_url, language) -> None:
    try:
        account_recovery.request_email_verification(
            db, user, base_url=base_url, language=language
        )
    except Exception:
        logger.exception("verification mail failed (registration unaffected)")


@router.post("/login", response_model=TokenResponse)
@limiter.limit("10/minute")
def login(request: Request, payload: LoginRequest, db: Session = Depends(get_db)):
    """
    Login with email and password

    - **email**: User's registered email
    - **password**: User's password

    Returns access token, refresh token, and user profile
    """
    return AuthService.login(db, payload)


@router.post("/refresh", response_model=TokenResponse)
def refresh_token(request: RefreshTokenRequest, db: Session = Depends(get_db)):
    """
    Refresh access token using refresh token

    - **refresh_token**: Valid refresh token

    Returns new access token, new refresh token, and user profile
    """
    return AuthService.refresh_token(db, request.refresh_token)


@router.get("/me", response_model=UserResponse)
def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
):
    """
    Get current authenticated user profile

    Requires valid access token in Authorization header:
    `Authorization: Bearer {access_token}`

    Returns user profile information
    """
    token = credentials.credentials
    user = AuthService.get_current_user(db, token)
    return UserResponse.model_validate(user)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """
    Logout current user

    Note: Since we're using stateless JWT, logout is handled client-side
    by deleting the stored tokens. This endpoint is provided for consistency.
    """
    # In a stateless JWT system, logout is handled by the client deleting tokens
    # If you want server-side token revocation, implement a token blacklist
    return None


@router.post("/google", response_model=TokenResponse)
def google_login(
    request: OAuthRequest,
    credentials: HTTPAuthorizationCredentials | None = Depends(_optional_bearer),
    db: Session = Depends(get_db),
):
    """
    Authenticate with Google Sign-In

    - **id_token**: Google ID token from the client
    - **username**: Optional username for new users

    The client should obtain the ID token using Google Sign-In SDK,
    then send it to this endpoint for verification and authentication.

    Configuration required:
    - Set GOOGLE_CLIENT_ID in backend settings
    - Configure Google OAuth 2.0 credentials in Google Cloud Console
    """
    return AuthService.oauth_google(db, request, credentials)


@router.post("/apple", response_model=TokenResponse)
def apple_login(request: OAuthRequest, db: Session = Depends(get_db)):
    """
    Authenticate with Apple Sign In

    - **id_token**: Apple ID token from the client
    - **username**: Optional username for new users

    The client should obtain the ID token using Sign in with Apple,
    then send it to this endpoint for verification and authentication.

    Configuration required:
    - Set APPLE_CLIENT_ID in backend settings
    - Configure Sign in with Apple in Apple Developer Portal
    - Implement Apple JWT token verification
    """
    return AuthService.oauth_apple(db, request)


class GuestLoginRequest(BaseModel):
    device_id: Optional[str] = None


@router.post("/guest", response_model=TokenResponse)
@limiter.limit("5/hour")
def guest_login(
    request: Request,
    payload: Optional[GuestLoginRequest] = None,
    db: Session = Depends(get_db),
):
    """
    Login as a guest user without authentication

    Creates a temporary guest account that allows users to access the app
    without registration. Guest accounts have limited functionality.

    - No email or password required
    - Generates a random guest username
    - Returns access token and guest user profile

    Guest users can later convert to regular users by registering.
    """
    return AuthService.guest_login(db, payload.device_id if payload else None)


@router.get("/me/export")
def export_my_data(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
):
    """
    GDPR data portability: export all personal data as JSON

    Returns user profile and benefits records associated with the account.
    """
    token = credentials.credentials
    user = AuthService.get_current_user(db, token)
    return AuthService.export_user_data(db, user)


# ══════════════════════════════════════════════════════════════════════════
# 找回密码 / 邮箱验证
#
# 在这之前**账号没有任何找回手段**:邮箱密码注册的人忘了密码就永久登不进去,
# 而通票挂在账号上 —— 付了钱的人拿不回自己买的东西,只能人工改库救。
#
# ⭐ 重置页由**本 API 自己吐 HTML**(下面的 GET /reset),不是发在官网上:
#   - 同源 → 不必为 gomuseum.app 开 CORS
#   - 不必发网站、不必等 Play 审核 → **已经装着 v27 的用户今天就能用**
#   （server-driven 优先:能改后端解决的,不靠发新 App 版本）
# ══════════════════════════════════════════════════════════════════════════


def _page(name: str, **subs: str) -> HTMLResponse:
    """渲染一个模板。占位符全部经 HTML 转义 —— 这几个值里有用户可控的令牌。"""
    text = (_TEMPLATES / name).read_text(encoding="utf-8")
    for key, value in subs.items():
        text = text.replace(f"__{key}__", _html.escape(value, quote=True))
    return HTMLResponse(text)


class PasswordResetRequest(BaseModel):
    email: EmailStr
    # 邮件正文的语言(en/fr/zh,其余回落 en)。**加法字段**,老 App 不传即默认。
    language: Optional[str] = None


class PasswordResetConfirm(BaseModel):
    token: str
    # 8 位下限与注册一致;上限防 bcrypt 的 72 字节截断问题被人拿来做怪
    new_password: str = Field(min_length=8, max_length=128)


@router.post("/password-reset/request", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit("5/hour")
def request_password_reset(
    request: Request,
    payload: PasswordResetRequest,
    db: Session = Depends(get_db),
):
    """申请重置密码,把带一次性链接的邮件发到该邮箱。

    ⚠️ **邮箱不存在也返回 204。** 若返 404,这个端点就成了账号枚举器 ——
    谁都能拿一份邮箱列表来问"你们这儿有哪些用户"。

    ⚠️ 但**发信真的失败要让用户看见**。这条路是他此刻唯一的出口;
    静默失败 = 他守着一封永远不来的邮件反复重试,而我们日志干净、监控全绿。

    ## 这两条会打架 —— 顺序是解法的一部分

    "查无此邮箱 → 204" 与 "发不出去 → 5xx" 放在一起,就又成了枚举器:
    **不存在的邮箱走不到发信那步,于是 204;存在的才可能 503。**
    2026-09-05 在 staging 实测撞见 —— 单测全绿,因为它们只在"SMTP 已配好"
    这一种配置下比较两者,而线上恰恰还没配。

    所以**配置检查必须放在查库之前**:没配 SMTP 时对谁都是 503,与账号无关。

    残留(明确接受):SMTP 配好了但那一刻发信失败(502)仍只可能发生在真实账号上。
    这条要在攻击者恰好赶上一次投递故障时才成立,而把它也抹平就等于放弃
    "让用户知道信没发出去" —— 后者对着急找回账号的人伤害更大。
    """
    # ⚠️ 顺序有意义:先于任何按邮箱查库的动作。见上面 docstring。
    if not mailer.is_configured():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"reason": "mail_not_configured"},
        )
    try:
        account_recovery.request_password_reset(
            db,
            payload.email,
            base_url=str(request.base_url).rstrip("/"),
            language=payload.language or request.headers.get("accept-language"),
        )
    except mailer.MailNotConfigured:
        # 兜底:走到这里说明配置在两次检查之间变了(或 send 自己判定未配置)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"reason": "mail_not_configured"},
        )
    except mailer.MailSendFailed:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={"reason": "mail_send_failed"},
        )
    return None


@router.get("/reset", response_class=HTMLResponse, include_in_schema=False)
def reset_password_page(token: str = "", db: Session = Depends(get_db)):
    """邮件里那条链接落在这里 —— 一张设置新密码的网页。

    这里**只看不消费**令牌:真正核销在下面的 confirm。
    先消费的话,用户打开页面却没提交(手滑关掉、想换个密码再想想),
    链接就已经废了,而他完全不知道为什么。
    """
    if (
        not token
        or account_recovery.peek(db, token, account_recovery.PURPOSE_PASSWORD_RESET)
        is None
    ):
        return _page(
            "notice.html",
            TITLE="链接已失效",
            BODY=(
                "这个重置链接已经过期或用过了。\n"
                "请回 App 重新申请一次。\n\n"
                "This reset link has expired or was already used.\n"
                "Please request a new one from the app."
            ),
        )
    return _page("reset_password.html", TOKEN=token)


@router.post("/password-reset/confirm", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit("10/hour")
def confirm_password_reset(
    request: Request,
    payload: PasswordResetConfirm,
    db: Session = Depends(get_db),
):
    """核销令牌并设置新密码。令牌无效/过期/已用过 → 400。

    ⚠️ **已知缺口(有意不做,不是漏了)**:重置后**不会踢掉已有会话**。
    要做需要给用户加一个令牌版本号并在校验热路径上检查它,而已经发出去的
    令牌没有该字段 —— 一上线就是全体用户被登出。
    这条债的触发场景是"忘了密码",不是"号被盗";会话失效属于后者,单独做。
    """
    if not account_recovery.confirm_password_reset(
        db, payload.token, payload.new_password
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"reason": "invalid_or_expired_token"},
        )
    return None


@router.post("/verify-email/request", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit("5/hour")
def request_email_verification(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
):
    """重发邮箱验证信(需登录)。已验证/无邮箱/未配置发信一律 204,不报错。"""
    user = AuthService.get_current_user(db, credentials.credentials)
    try:
        account_recovery.request_email_verification(
            db,
            user,
            base_url=str(request.base_url).rstrip("/"),
            language=request.headers.get("accept-language"),
        )
    except mailer.MailNotConfigured:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"reason": "mail_not_configured"},
        )
    return None


@router.get("/verify-email", response_class=HTMLResponse, include_in_schema=False)
def confirm_email_verification(token: str = "", db: Session = Depends(get_db)):
    """验证信里那条链接落在这里。幂等:重复点开只会看到"链接已失效"。"""
    if token and account_recovery.confirm_email_verification(db, token):
        return _page(
            "notice.html",
            TITLE="邮箱已确认",
            BODY=(
                "可以关掉这个页面了。\n\n"
                "Your email address is confirmed.\nYou can close this page."
            ),
        )
    return _page(
        "notice.html",
        TITLE="链接已失效",
        BODY=(
            "这个确认链接已经过期或用过了。\n"
            "可以在 App 的设置里重新发送。\n\n"
            "This link has expired or was already used.\n"
            "You can send a new one from the app's settings."
        ),
    )


@router.delete("/me", status_code=status.HTTP_204_NO_CONTENT)
def delete_my_account(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
):
    """
    GDPR right to erasure / App Store account deletion requirement

    Permanently deletes the account and all associated personal data
    (profile, benefits). This action is irreversible.
    """
    token = credentials.credentials
    user = AuthService.get_current_user(db, token)
    AuthService.delete_user_account(db, user)
    return None
