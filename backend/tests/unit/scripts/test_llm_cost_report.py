"""成本报告按 llm_usage 的价目表计价(R8/R11):旧 PRICES 漏了 Claude,算成 0。"""

from datetime import date

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import settings
from app.core.database import Base
from app.models.llm_usage import LLMUsage
from scripts.llm_cost_report import report


@pytest.fixture()
def db():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(bind=engine, tables=[LLMUsage.__table__])
    s = sessionmaker(bind=engine)()
    yield s
    s.close()


def test_report_prices_claude_and_flags_unknown_model(db, monkeypatch):
    today = date.today()
    db.add_all(
        [
            LLMUsage(
                day=today,
                channel="gate@app",
                model="claude-haiku-5-5",
                calls=1,
                tokens_in=1_000_000,
                tokens_out=0,
            ),
            LLMUsage(
                day=today,
                channel="vision@app",
                model="new-model",
                calls=1,
                tokens_in=1000,
                tokens_out=0,
            ),
        ]
    )
    db.commit()
    monkeypatch.setattr(settings, "LLM_PRICES", {"claude-haiku-5-5": (1.0, 5.0)})
    lines = report(db, 30).splitlines()
    claude = next(x for x in lines if "claude-haiku-5-5" in x)
    new = next(x for x in lines if "new-model" in x)
    assert "1.00" in claude
    assert new.endswith(" ?")
