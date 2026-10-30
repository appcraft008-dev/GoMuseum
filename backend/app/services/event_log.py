"""事件记录。**记账失败绝不破坏业务** —— 与 llm_usage 同纪律。"""

import ipaddress
import logging

from app.models.app_event import AppEvent

logger = logging.getLogger(__name__)


def log_event(
    db, name: str, *, user_id=None, device_id=None, museum_slug=None, **props
):
    """写一条事件。异常吞掉(埋点挂了不能连累识别/购买)。

    ⚠️ **绝不 rollback 调用方的事务**。曾经在异常分支直接 `db.rollback()`,
    结果是:埋点写失败 → 把调用方**尚未提交的业务数据一起回滚**。
    实测后果——游客登录时刚建的 UserBenefits 被回滚,同设备第二次登录
    又建新账号,防刷额度直接失效。"记账失败绝不破坏业务"必须落到实处:
    用 SAVEPOINT 把 AppEvent 的写入圈起来,失败只回滚这个存档点。
    """
    try:
        with db.begin_nested():  # SAVEPOINT:失败只回滚这一段
            db.add(
                AppEvent(
                    name=name,
                    user_id=user_id,
                    device_id=device_id,
                    museum_slug=museum_slug,
                    props=props or None,
                )
            )
    except Exception:
        logger.exception("log_event failed (business data untouched): %s", name)
        return
    try:
        db.commit()
    except Exception:
        logger.exception("commit after log_event failed: %s", name)


# Play 预发布报告/审核员的测试机从这几段 Google 网段登录(10-30 prod nginx 实测)。
# ponytail: 写死实测网段;漏标新网段时补这里,要全量再拉 goog.json
_GOOGLE_PROBE_NETS = tuple(
    ipaddress.ip_network(n)
    for n in ("66.249.64.0/19", "74.125.0.0/16", "66.102.0.0/20", "192.178.0.0/15")
)


def is_google_probe_ip(ip) -> bool:
    try:
        addr = ipaddress.ip_address(ip)
    except (TypeError, ValueError):
        return False
    return any(addr in n for n in _GOOGLE_PROBE_NETS)


def mark_probe_login(db, request, resp, device_id=None):
    """登录来自 Google 网段 → 记 probe_login,运营报告据此从真实用户里剔除。"""
    ip = request.client.host if request.client else None
    if is_google_probe_ip(ip):
        log_event(db, "probe_login", user_id=str(resp.user.id), device_id=device_id)
    return resp
