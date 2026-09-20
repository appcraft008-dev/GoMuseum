"""`daily_budget_exhausted` 自身的判断力自检。

上面那条端点测试把这个函数整个 monkeypatch 掉了 —— 那测的是"闸接线接对了没有"，
**测不到闸自己判得对不对**。按 [[verify-tools-before-trusting-them]]：判定类逻辑
必须先用已知的正/负样本验证它的判断力，再信它。

这里的正/负样本是"今天写的段" vs "昨天写的段" —— 一个日期边界最容易写错的地方
（比如误用 `>= now() - 1 day` 就会把昨天下午的也算进今天）。
"""

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base
from app.models.content import ObjectContentSection
from app.models.museum import Museum
from app.models.museum_object import MuseumObject
from app.services.enrichment.lazy import daily_budget_exhausted


@pytest.fixture()
def db():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(
        bind=engine,
        tables=[
            Museum.__table__,
            MuseumObject.__table__,
            ObjectContentSection.__table__,
        ],
    )
    s = sessionmaker(bind=engine)()
    m = Museum(slug="x", name_en="X")
    s.add(m)
    s.flush()
    obj = MuseumObject(museum_id=m.id, qid="Q1")
    s.add(obj)
    s.commit()
    s.obj_id = obj.id
    yield s
    s.close()


def _add(s, n, *, at):
    for i in range(n):
        s.add(
            ObjectContentSection(
                object_id=s.obj_id,
                language="en",
                section_code=f"s{at.timestamp()}-{i}",
                body="x",
                generated_at=at,
            )
        )
    s.commit()


def _today():
    return datetime.now(timezone.utc).replace(
        hour=12, minute=0, second=0, microsecond=0
    )


def test_empty_db_is_not_exhausted(db):
    assert daily_budget_exhausted(db, cap=3) is False


def test_below_cap_is_not_exhausted(db):
    _add(db, 2, at=_today())
    assert daily_budget_exhausted(db, cap=3) is False


def test_at_cap_is_exhausted(db):
    """边界取 `>=` —— 恰好等于 cap 就该停，不是超过才停。"""
    _add(db, 3, at=_today())
    assert daily_budget_exhausted(db, cap=3) is True


def _midnight():
    return datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)


def test_yesterdays_sections_do_not_count(db):
    """负样本：昨天生成的段不该占今天的预算。

    ⚠️ 取样点刻意是「**今天 0 点前一秒**」，不是"昨天中午"。
    昨天中午那个样本**没有判断力**：把实现写成"最近 24 小时"的话，只要当前时刻
    晚于中午，昨天中午也落在 24 小时窗口外，测试照样绿 —— 那就等于没测。
    0 点前一秒则是两种实现唯一分歧的地方：按"今天起"算它不该数，
    按"最近 24 小时"算它必然要数。

    （残留：若测试恰好在 23:59:59 之后运行，"最近 24 小时"实现也会放过它。
    这一秒不值得为它引入 freezegun。）
    """
    _add(db, 50, at=_midnight() - timedelta(seconds=1))
    assert daily_budget_exhausted(db, cap=3) is False


def test_sections_at_exactly_midnight_do_count(db):
    """正样本，与上一条配对把边界钉死在 0 点整。

    只有上一条的话，一个"永远返回 False"的实现也会绿。
    """
    _add(db, 3, at=_midnight())
    assert daily_budget_exhausted(db, cap=3) is True


def test_generated_at_null_does_not_count(db):
    """从没生成过的行（只有正文、没有 generated_at）不该被算进花费。"""
    db.add(
        ObjectContentSection(
            object_id=db.obj_id, language="fr", section_code="nogen", body="x"
        )
    )
    db.commit()
    assert daily_budget_exhausted(db, cap=1) is False
