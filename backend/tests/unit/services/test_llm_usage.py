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


def test_report_aggregates(session):
    record_llm_usage("tts", "tts-1", 5000, 0, db=session)
    record_llm_usage("gate", "gpt-4o-mini", 1000, 200, db=session)
    out = report(session, days=7)
    assert "tts" in out and "gate" in out and "合计" in out
