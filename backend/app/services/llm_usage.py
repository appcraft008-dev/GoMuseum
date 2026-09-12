"""LLM 用量记账 helper(成本工程①)。记账绝不拖垮生成:任何失败吞掉只告警。"""

from __future__ import annotations

import logging
from datetime import date

logger = logging.getLogger(__name__)


def _insert_for(db):
    """按方言选 insert 构造器(两家的 on_conflict_do_update API 相同)。

    ⚠️ 单测跑 SQLite、prod 跑 PG。走方言分支是为了让**测试和生产是同一套
    upsert 语义**,而不是只留一个编译断言 —— 2026-09-12 刚踩过反面教材:
    `has_key()` 是 PG-only,833 个单测在 SQLite 上全绿,部署到真 PG 才炸。
    """
    from sqlalchemy.dialects import postgresql, sqlite

    name = db.get_bind().dialect.name
    return postgresql.insert if name == "postgresql" else sqlite.insert


def usage_upsert(db, channel: str, model: str, tokens_in: int, tokens_out: int):
    """构造那条 upsert。抽出来是为了能直接断言它的 SQL 形状:
    增量得出现在语句里(`llm_usage.calls + 1`),而不是在 Python 里算完再写。
    """
    from app.models.llm_usage import LLMUsage

    stmt = _insert_for(db)(LLMUsage).values(
        day=date.today(),
        channel=channel,
        model=model,
        calls=1,
        tokens_in=int(tokens_in or 0),
        tokens_out=int(tokens_out or 0),
    )
    return stmt.on_conflict_do_update(
        index_elements=["day", "channel", "model"],
        set_={
            "calls": LLMUsage.calls + 1,
            "tokens_in": LLMUsage.tokens_in + stmt.excluded.tokens_in,
            "tokens_out": LLMUsage.tokens_out + stmt.excluded.tokens_out,
        },
    )


def record_llm_usage(
    channel: str, model: str, tokens_in: int, tokens_out: int, db=None
) -> None:
    """day×channel×model 累加一次调用。db 注入可测;None 时开独立短会话
    (不依赖调用方事务,生成 rollback 不吞记账)。

    ⚠️ **一条 upsert,不要改回「先 get 再 +=」**。两个 worker 并发时那种写法有两个坑:
    ① 行不存在时双双 INSERT → `UniqueViolation`(prod 实测每天首次调用会撞一次);
    ② 更阴的是行已存在时双双 read-modify-write → **计数静默丢失,连报错都没有**。
    增量必须由数据库算(`calls = llm_usage.calls + 1`),不能由 Python 算。
    """
    own = db is None
    if own:
        from app.core.database import SessionLocal

        db = SessionLocal()
    try:
        db.execute(usage_upsert(db, channel, model, tokens_in, tokens_out))
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
