"""事件记录。**记账失败绝不破坏业务** —— 与 llm_usage 同纪律。"""

import logging

from app.models.app_event import AppEvent

logger = logging.getLogger(__name__)


def log_event(
    db, name: str, *, user_id=None, device_id=None, museum_slug=None, **props
):
    """写一条事件。异常吞掉(埋点挂了不能连累识别/购买)。"""
    try:
        db.add(
            AppEvent(
                name=name,
                user_id=user_id,
                device_id=device_id,
                museum_slug=museum_slug,
                props=props or None,
            )
        )
        db.commit()
    except Exception:
        logger.exception("log_event failed: %s", name)
        try:
            db.rollback()
        except Exception:
            pass
