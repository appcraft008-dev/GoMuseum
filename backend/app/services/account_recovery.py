"""找回密码与邮箱验证。

## 为什么这是"上线前必须有"的东西

通票挂在账号上。用邮箱密码注册的用户忘了密码 → 永久登不进去 →
**付了钱的人拿不回自己买的东西**,而我们只能靠人工改库救。
触发条件不是"将来某天",是第一个真实付费用户忘记密码。

## 几条不显然的取舍

- **只给「已经有密码」的账号发重置信。** 纯 Google/Apple 登录的账号没有密码,
  给它"重置"等于**凭一封邮件新造一把绕过 Google 二步验证的钥匙** ——
  账号安全被降到"邮箱有多安全",而用户从没要求过这个。他们有能用的登录方式。

- **无论如何都返回 204。** 若"邮箱不存在"返 404,这个端点就成了**账号枚举器**:
  谁都能拿一份邮箱列表来问"你们这儿有哪些用户"。

- **发信失败必须让用户看见(502)。** 找回密码是他此刻唯一的路;
  静默失败 = 他守着一封永远不来的邮件反复重试,而我们日志干净、监控全绿。

- **令牌只存哈希、用一次即废、旧的重发即作废。** 见 models/auth_token.py。
"""

from __future__ import annotations

import hashlib
import logging
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional
from urllib.parse import quote

from app.core.config import settings
from app.core.security import hash_password
from app.models.auth_token import (
    PURPOSE_EMAIL_VERIFY,
    PURPOSE_PASSWORD_RESET,
    AuthToken,
)
from app.models.user import User
from app.services import mailer

logger = logging.getLogger(__name__)

# 邮件正文只有三种语言:商店条目就是 en/fr/zh,内容也只有这三种。
# 认不出的语言一律回落英文 —— 宁可给一封看得懂的英文信,不给一封空的。
DEFAULT_LANG = "en"
SUPPORTED_LANGS = ("en", "fr", "zh")

_RESET_MAIL = {
    "en": (
        "Reset your GoMuseum password",
        "Open this link to choose a new password:\n\n{link}\n\n"
        "The link expires in {minutes} minutes and can be used once.\n"
        "If you didn't ask for this, you can ignore this email — "
        "your password stays unchanged.",
    ),
    "fr": (
        "Réinitialiser votre mot de passe GoMuseum",
        "Ouvrez ce lien pour choisir un nouveau mot de passe :\n\n{link}\n\n"
        "Le lien expire dans {minutes} minutes et ne peut servir qu'une fois.\n"
        "Si vous n'êtes pas à l'origine de cette demande, ignorez ce message — "
        "votre mot de passe reste inchangé.",
    ),
    "zh": (
        "重设 GoMuseum 密码",
        "打开这个链接设置新密码：\n\n{link}\n\n"
        "链接 {minutes} 分钟内有效，只能用一次。\n"
        "如果不是你本人操作，忽略这封邮件即可，密码不会有任何变化。",
    ),
}

_VERIFY_MAIL = {
    "en": (
        "Confirm your GoMuseum email",
        "Open this link to confirm this address:\n\n{link}\n\n"
        "The link expires in {minutes} minutes.\n"
        "Confirming keeps password recovery working if you ever need it.",
    ),
    "fr": (
        "Confirmez votre adresse e-mail GoMuseum",
        "Ouvrez ce lien pour confirmer cette adresse :\n\n{link}\n\n"
        "Le lien expire dans {minutes} minutes.\n"
        "La confirmation garantit que la récupération de mot de passe "
        "fonctionnera le jour où vous en aurez besoin.",
    ),
    "zh": (
        "确认你的 GoMuseum 邮箱",
        "打开这个链接确认这个邮箱地址：\n\n{link}\n\n"
        "链接 {minutes} 分钟内有效。\n"
        "确认之后，万一将来需要找回密码才走得通。",
    ),
}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _aware(dt: Optional[datetime]) -> Optional[datetime]:
    """SQLite 不存时区,Postgres 存。naive 一律按 UTC 解读(服务端时间为准)。"""
    if dt is None or dt.tzinfo is not None:
        return dt
    return dt.replace(tzinfo=timezone.utc)


def _digest(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _lang(code: Optional[str]) -> str:
    """把 `zh-Hans` / `fr_FR` 这类归一到我们有文案的三种之一。"""
    if not code:
        return DEFAULT_LANG
    base = code.replace("_", "-").split("-")[0].lower()
    return base if base in SUPPORTED_LANGS else DEFAULT_LANG


def issue(db, user_id: str, purpose: str, ttl_minutes: int) -> str:
    """签发一张一次性令牌,返回**明文**(只有这一次能拿到,库里只有哈希)。

    同一用户同一用途下**尚未使用的旧令牌一并作废**:重发之后旧链接还能用的话,
    用户收件箱里就积着好几把有效钥匙,而他以为只有最新那封算数。
    """
    db.query(AuthToken).filter(
        AuthToken.user_id == user_id,
        AuthToken.purpose == purpose,
        AuthToken.used_at.is_(None),
    ).update({"used_at": _now()}, synchronize_session=False)

    token = secrets.token_urlsafe(32)
    db.add(
        AuthToken(
            user_id=user_id,
            purpose=purpose,
            token_hash=_digest(token),
            expires_at=_now() + timedelta(minutes=ttl_minutes),
        )
    )
    db.commit()
    return token


def peek(db, token: str, purpose: str) -> Optional[AuthToken]:
    """令牌可用就返回它,否则 None。**不消费** —— 给"先渲染页面"用。"""
    row = (
        db.query(AuthToken)
        .filter(
            AuthToken.token_hash == _digest(token),
            AuthToken.purpose == purpose,
        )
        .one_or_none()
    )
    if row is None or row.used_at is not None:
        return None
    expires = _aware(row.expires_at)
    return None if expires is not None and expires <= _now() else row


def consume(db, token: str, purpose: str) -> Optional[AuthToken]:
    """核销令牌。成功返回该行,并**当场标记已用**。"""
    row = peek(db, token, purpose)
    if row is None:
        return None
    row.used_at = _now()
    db.commit()
    return row


def _link(base_url: Optional[str], path: str, token: str) -> str:
    base = (getattr(settings, "PUBLIC_API_BASE_URL", None) or base_url or "").rstrip(
        "/"
    )
    return f"{base}{path}?token={quote(token)}"


# ────────────────────────────────────────────────────────────── 找回密码


def request_password_reset(db, email: str, *, base_url=None, language=None) -> None:
    """发一封重置信。**无论结果如何都不告诉调用方账号存不存在。**

    抛 MailNotConfigured / MailSendFailed 表示"信确实没发出去" ——
    那必须让用户看见,而它与"这个邮箱没注册过"是两回事,不会泄漏账号存在与否
    (因为不存在的邮箱压根不会走到发信这一步)。
    """
    user = db.query(User).filter(User.email == email).one_or_none()
    if user is None or user.is_guest or not user.is_active:
        return
    if not user.password_hash:
        # 纯 OAuth 账号。给它发重置 = 凭一封邮件新造一把绕过 Google 二步验证的
        # 钥匙,把账号安全降到"邮箱有多安全",而用户从没要求过。他有能用的登录方式。
        logger.info("password reset skipped for OAuth-only account")
        return

    ttl = settings.PASSWORD_RESET_TTL_MINUTES
    token = issue(db, str(user.id), PURPOSE_PASSWORD_RESET, ttl)
    subject, body = _RESET_MAIL[_lang(language)]
    mailer.send(
        user.email,
        subject,
        body.format(link=_link(base_url, "/api/v1/auth/reset", token), minutes=ttl),
    )


def confirm_password_reset(db, token: str, new_password: str) -> bool:
    """核销令牌并改密码。令牌无效/过期/用过 → False。"""
    row = consume(db, token, PURPOSE_PASSWORD_RESET)
    if row is None:
        return False
    import uuid as _uuid

    try:
        uid = _uuid.UUID(row.user_id)
    except ValueError:
        return False
    user = db.query(User).filter(User.id == uid).one_or_none()
    if user is None or not user.is_active:
        return False
    user.password_hash = hash_password(new_password)
    # 走到这一步说明他确实收得到这个邮箱的信 —— 顺带把邮箱标成已验证,
    # 省掉一次毫无意义的二次确认。
    if not user.is_verified:
        user.is_verified = True
        user.email_verified_at = datetime.utcnow()
    db.commit()
    return True


# ────────────────────────────────────────────────────────────── 邮箱验证


def request_email_verification(db, user: User, *, base_url=None, language=None) -> bool:
    """发一封验证信。没邮箱/已验证/未配置发信 → False(调用方按"没发"处理)。

    ⚠️ **注册时调用它绝不能让注册失败**:发信是锦上添花,注册是主线。
    """
    if not user.email or user.is_guest or user.is_verified:
        return False
    if not mailer.is_configured():
        return False
    ttl = settings.EMAIL_VERIFY_TTL_MINUTES
    token = issue(db, str(user.id), PURPOSE_EMAIL_VERIFY, ttl)
    subject, body = _VERIFY_MAIL[_lang(language)]
    try:
        mailer.send(
            user.email,
            subject,
            body.format(
                link=_link(base_url, "/api/v1/auth/verify-email", token), minutes=ttl
            ),
        )
    except mailer.MailSendFailed:
        return False
    return True


def confirm_email_verification(db, token: str) -> bool:
    row = consume(db, token, PURPOSE_EMAIL_VERIFY)
    if row is None:
        return False
    import uuid as _uuid

    try:
        uid = _uuid.UUID(row.user_id)
    except ValueError:
        return False
    user = db.query(User).filter(User.id == uid).one_or_none()
    if user is None:
        return False
    user.is_verified = True
    user.email_verified_at = datetime.utcnow()
    db.commit()
    return True
