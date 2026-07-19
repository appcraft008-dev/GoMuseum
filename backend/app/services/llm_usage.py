"""LLM 用量记账 helper(成本工程①)。记账绝不拖垮生成:任何失败吞掉只告警。"""

from __future__ import annotations

import logging
from datetime import date

logger = logging.getLogger(__name__)


def record_llm_usage(
    channel: str, model: str, tokens_in: int, tokens_out: int, db=None
) -> None:
    """day×channel×model 累加一次调用。db 注入可测;None 时开独立短会话
    (不依赖调用方事务,生成 rollback 不吞记账)。"""
    from app.models.llm_usage import LLMUsage

    own = db is None
    if own:
        from app.core.database import SessionLocal

        db = SessionLocal()
    try:
        row = db.get(LLMUsage, (date.today(), channel, model))
        if row is None:
            row = LLMUsage(
                day=date.today(),
                channel=channel,
                model=model,
                calls=0,
                tokens_in=0,
                tokens_out=0,
            )
            db.add(row)
        row.calls += 1
        row.tokens_in += int(tokens_in or 0)
        row.tokens_out += int(tokens_out or 0)
        db.commit()
    except Exception:  # 观测性永不破坏业务
        logger.warning("record_llm_usage failed (%s/%s)", channel, model, exc_info=True)
        try:
            db.rollback()
        except Exception:
            pass
    finally:
        if own:
            db.close()
