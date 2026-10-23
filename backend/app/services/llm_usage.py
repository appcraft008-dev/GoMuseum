"""LLM 用量记账 helper(成本工程①)。记账绝不拖垮生成:任何失败吞掉只告警。"""

from __future__ import annotations

import logging
from datetime import date, datetime, timezone

logger = logging.getLogger(__name__)

# 模型 → (输入, 输出) $/百万 token;TTS 为 $/百万字、输出 0。2026-10-23 逐条核对官方价目页:
# Claude: claude-api skill 模型表(Haiku 5.5 为提示 ≤10 万 token 的价,我们的调用都在此内)
# OpenAI: https://developers.openai.com/api/docs/pricing(Standard / Batch / tts-1)
# Google: https://cloud.google.com/text-to-speech/pricing(Chirp 3: HD)
# .env 的 LLM_PRICES 只写要补或要改的模型,和这里合并(R8)。
DEFAULT_LLM_PRICES: dict[str, tuple[float, float]] = {
    "claude-haiku-5-5": (0.10, 0.50),
    "claude-sonnet-5-5": (2.0, 10.0),
    "gpt-6-luna": (0.10, 0.50),
    "gpt-6.1-sol": (2.0, 10.0),
    "gpt-4o": (2.50, 10.0),
    "gpt-4o-mini": (0.15, 0.60),
    "gpt-4o@batch": (1.25, 5.0),  # Batch API 半价(成本工程②)
    "tts-1": (15.0, 0.0),
    "google-chirp3-hd": (30.0, 0.0),  # 每月前 100 万字免费,账上不扣
}


def cost_usd(model: str, tokens_in: int, tokens_out: int) -> tuple[float, bool]:
    """(美元, 模型是否在价目里)。未知模型按最贵价计(spec §4.1):输入、输出各取
    大模型条目(输出价 > 0)里的最高价;TTS 按字计价不参与,否则虚高 12 倍(R11)。"""
    from app.core.config import settings

    prices = {**DEFAULT_LLM_PRICES, **settings.LLM_PRICES}
    known = model in prices
    if known:
        pin, pout = prices[model]
    else:
        llm = [v for v in prices.values() if v[1] > 0]
        pin = max((v[0] for v in llm), default=0.0)
        pout = max((v[1] for v in llm), default=0.0)
    return (tokens_in or 0) / 1e6 * pin + (tokens_out or 0) / 1e6 * pout, known


# 来源后缀(P3-14③):在线服务进程(懒生成/懒翻译/问答,用户触发)里记成 "translate@app",
# 离线脚本照旧不带后缀。由 main._startup 置位。按进程分而不按调用链传标记:
# 生成内部有线程池,contextvar 过不去。
ORIGIN_SUFFIX = ""


def _insert_for(db):
    """按方言选 insert 构造器(两家的 on_conflict_do_update API 相同)。

    ⚠️ 单测跑 SQLite、prod 跑 PG。走方言分支是为了让**测试和生产是同一套
    upsert 语义**,而不是只留一个编译断言 —— 2026-09-12 刚踩过反面教材:
    `has_key()` 是 PG-only,833 个单测在 SQLite 上全绿,部署到真 PG 才炸。
    """
    from sqlalchemy.dialects import postgresql, sqlite

    name = db.get_bind().dialect.name
    return postgresql.insert if name == "postgresql" else sqlite.insert


def utc_today() -> date:
    """记账计日一律按 UTC(spec §4.1),不随容器时区。"""
    return datetime.now(timezone.utc).date()


def usage_upsert(db, channel: str, model: str, tokens_in: int, tokens_out: int):
    """构造那条 upsert。抽出来是为了能直接断言它的 SQL 形状:
    增量得出现在语句里(`llm_usage.calls + 1`),而不是在 Python 里算完再写。
    """
    from app.models.llm_usage import LLMUsage

    stmt = _insert_for(db)(LLMUsage).values(
        day=utc_today(),
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
        db.execute(
            usage_upsert(db, channel + ORIGIN_SUFFIX, model, tokens_in, tokens_out)
        )
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
