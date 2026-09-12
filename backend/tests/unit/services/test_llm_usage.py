"""LLM 用量记账:day×channel×model 累加;失败吞掉不破坏业务;报告聚合。"""

from datetime import date

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base
from app.models.llm_usage import LLMUsage
from app.services.llm_usage import record_llm_usage
from scripts.llm_cost_report import report


@pytest.fixture()
def session():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(bind=engine, tables=[LLMUsage.__table__])
    yield sessionmaker(bind=engine)()


def test_record_accumulates_same_key(session):
    record_llm_usage("gate", "gpt-4o-mini", 100, 20, db=session)
    record_llm_usage("gate", "gpt-4o-mini", 50, 10, db=session)
    row = session.get(LLMUsage, (date.today(), "gate", "gpt-4o-mini"))
    assert row.calls == 2 and row.tokens_in == 150 and row.tokens_out == 30


def test_record_separates_channels_and_models(session):
    record_llm_usage("gate", "gpt-4o-mini", 1, 1, db=session)
    record_llm_usage("translate", "gpt-4o-mini", 2, 2, db=session)
    record_llm_usage("translate", "gpt-4o", 3, 3, db=session)
    assert session.query(LLMUsage).count() == 3


def test_record_swallows_failure(session):
    session.close()  # 制造坏 session
    record_llm_usage("gate", "m", 1, 1, db=session)  # 不抛即过


def test_increment_happens_in_the_database_not_in_python(session):
    """增量必须写在 SQL 里(`llm_usage.calls + 1`),不能先读到 Python 再加。

    并发下"先 get 再 +=" 有两个坑,而且第二个不会报错:
    ① 行不存在时两个 worker 双双 INSERT → UniqueViolation(prod 每天首次调用撞一次);
    ② 行已存在时双双 read-modify-write → **计数静默丢失**。
    单测里模拟不出真并发(SQLite 共享同一连接),所以退而钉住语句形状 ——
    有人改回 Python 端增量,这条就红。
    """
    from sqlalchemy.dialects import postgresql, sqlite

    from app.services.llm_usage import usage_upsert

    for dialect in (postgresql.dialect(), sqlite.dialect()):
        sql = str(
            usage_upsert(session, "gate", "gpt-4o-mini", 7, 3).compile(dialect=dialect)
        )
        assert "ON CONFLICT" in sql.upper(), f"{dialect.name}: 不是 upsert"
        # 计数由数据库自增
        assert "llm_usage.calls + " in sql, f"{dialect.name}: 增量没发生在 DB 端"
        # token 取本次传入值(excluded),不是把旧值再写一遍
        assert "excluded" in sql.lower(), f"{dialect.name}: 没用 excluded"


def test_upsert_follows_the_session_dialect(session):
    """方言选错会在 prod 才炸(SQLite 单测全绿 → 真 PG AttributeError,2026-09-12 踩过)。"""
    from app.services.llm_usage import _insert_for

    assert _insert_for(session).__module__.endswith("sqlite.dml")


def test_report_aggregates(session):
    record_llm_usage("tts", "tts-1", 5000, 0, db=session)
    record_llm_usage("gate", "gpt-4o-mini", 1000, 200, db=session)
    out = report(session, days=7)
    assert "tts" in out and "gate" in out and "合计" in out
