"""发信。stdlib `smtplib`,零新依赖、不锁厂商。

Resend / SendGrid / Mailgun / Postmark 全都提供 SMTP,换服务商只改 .env 里那几个
变量。用某一家的 HTTP SDK 反而会把"发信"这件小事焊死在一个供应商上。

## 两条纪律

- **未配置 = 明确失败**,绝不静默丢弃。静默丢弃的后果是用户守着一封永远不来的
  邮件反复重试,而我们这侧日志干净、监控全绿 —— 这种"看起来好着"的故障最难发现。
- **发信内容里不带任何多余信息**。这封信会在收件箱里躺很久,且可能被转发。
"""

from __future__ import annotations

import logging
import smtplib
import ssl
from email.message import EmailMessage

from app.core.config import settings

logger = logging.getLogger(__name__)


class MailNotConfigured(Exception):
    """没有 SMTP 配置。调用方必须让用户看见失败,不能假装发出去了。"""


class MailSendFailed(Exception):
    """连上了但没发成。同样必须让用户看见 —— 找回密码是他此刻唯一的路。"""


def is_configured() -> bool:
    return bool(getattr(settings, "SMTP_HOST", None))


def send(to: str, subject: str, body: str) -> None:
    """发一封纯文本邮件。**同步阻塞**。

    纯文本而非 HTML:找回密码这类邮件里 HTML 只增加被判垃圾邮件的概率,
    以及一条渲染差异的排查线索。内容就一句话加一条链接,不需要排版。
    """
    if not is_configured():
        raise MailNotConfigured("SMTP_HOST 未配置")

    msg = EmailMessage()
    msg["From"] = settings.MAIL_FROM
    msg["To"] = to
    msg["Subject"] = subject
    msg.set_content(body)

    host = settings.SMTP_HOST
    port = settings.SMTP_PORT
    user = getattr(settings, "SMTP_USER", None)
    password = getattr(settings, "SMTP_PASSWORD", None)

    try:
        if settings.SMTP_STARTTLS:
            with smtplib.SMTP(host, port, timeout=15) as s:
                s.starttls(context=ssl.create_default_context())
                if user:
                    s.login(user, password or "")
                s.send_message(msg)
        else:
            # 465 等隐式 TLS 端口
            with smtplib.SMTP_SSL(
                host, port, timeout=15, context=ssl.create_default_context()
            ) as s:
                if user:
                    s.login(user, password or "")
                s.send_message(msg)
    except Exception as e:
        # ⚠️ 不要把 e 原样透给用户:SMTP 的错误信息里常带账号名与主机名。
        logger.exception("发信失败 to=%s subject=%s", to, subject)
        raise MailSendFailed(str(e)) from e
