"""运维告警邮件,发到 OPS_ALERT_EMAIL。

只写日志的故障没人看见(探活两个月没人发现 Joconde 断供就是这么来的),
要让人看见的事走这里。
"""

from __future__ import annotations

import logging
import threading
import time

from app.core.config import settings
from app.services import mailer

logger = logging.getLogger(__name__)

THROTTLE_S = 6 * 3600
_last: dict[str, float] = {}
_lock = threading.Lock()


def send(subject: str, body: str) -> None:
    """同步发;没配收件人或发不出去都抛,调用方决定怎么让人看见失败。"""
    to = getattr(settings, "OPS_ALERT_EMAIL", None)
    if not to:
        raise mailer.MailNotConfigured("OPS_ALERT_EMAIL 未配置")
    mailer.send(to, subject, body)


def alert_throttled(key: str, subject: str, body: str) -> None:
    """请求路径用:同 key 每进程 6h 最多一封,后台线程发,不阻塞、不抛。"""
    now = time.time()
    with _lock:
        if now - _last.get(key, float("-inf")) < THROTTLE_S:
            return
        _last[key] = now

    def _go():
        try:
            send(subject, body)
        except Exception:
            logger.exception("ops alert not sent: %s", subject)

    threading.Thread(target=_go, daemon=True, name="ops-alert").start()
