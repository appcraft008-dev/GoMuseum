"""事件记录。**记账失败绝不破坏业务** —— 与 llm_usage 同纪律。"""

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
