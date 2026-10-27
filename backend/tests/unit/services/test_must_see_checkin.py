"""必看打卡:判据、按 30 天切轮、打满落勋章(spec 2026-10-27 §五.2-3)。

造行一律 museum_slug=None —— App 走全局识别端点,线上事件行就是这样(审查 C1)。
"""

from datetime import datetime, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base
from app.models.must_see_medal import MustSeeMedal
from app.models.recognition_event import RecognitionEvent
from app.services import must_see
from app.services.must_see_checkin import progress

T0 = datetime(2026, 10, 1, 10, 0, 0)
LIST = ["Q1", "Q2", "Q3"]


@pytest.fixture()
def db(monkeypatch):
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(
        bind=engine, tables=[RecognitionEvent.__table__, MustSeeMedal.__table__]
    )
    monkeypatch.setitem(must_see.MUST_SEE, "x", list(LIST))
    s = sessionmaker(bind=engine)()
    yield s
    s.close()


def _ev(db, qid, at, *, user="u", capture="camera", outcome="match", **kw):
    db.add(
        RecognitionEvent(
            museum_slug=None,
            phash=f"p-{qid}-{at.isoformat()}",
            outcome=outcome,
            top_qid=qid,
            engine="vector",
            user_id=user,
            capture=capture,
            created_at=at,
            **kw,
        )
    )
    db.commit()


def _p(db, now, user="u"):
    return progress(db, user, "x", now=now)


def test_only_camera_counts(db):
    _ev(db, "Q1", T0, capture=None)
    _ev(db, "Q2", T0, capture="gallery")
    _ev(db, "Q3", T0, capture="camera")
    assert set(_p(db, T0)["checked"]) == {"Q3"}


def test_search_confirm_and_rejected_and_anonymous_excluded(db):
    _ev(db, "Q1", T0, outcome="candidates", confirmed_qid="Q1", confirm_source="search")
    _ev(db, "Q2", T0, rejected_qids=["Q2"])
    _ev(db, "Q3", T0, user=None)
    _ev(db, "Q3", T0, outcome="candidates")  # 未确认的候选不算
    assert _p(db, T0)["checked"] == {}
    _ev(
        db,
        "Q3",
        T0,
        outcome="candidates",
        confirmed_qid="Q3",
        confirm_source="candidates",
    )
    assert set(_p(db, T0)["checked"]) == {"Q3"}


def test_qid_outside_list_ignored(db):
    _ev(db, "Q99", T0)
    assert _p(db, T0)["checked"] == {}


def test_round_split_boundary(db):
    _ev(db, "Q1", T0)
    _ev(db, "Q2", T0 + timedelta(days=30))  # 恰好 30 天:同轮
    p = _p(db, T0 + timedelta(days=30))
    assert set(p["checked"]) == {"Q1", "Q2"}
    _ev(db, "Q3", T0 + timedelta(days=60, seconds=1))  # 距上次 30 天+1 秒:新轮
    p = _p(db, T0 + timedelta(days=60, seconds=1))
    assert set(p["checked"]) == {"Q3"}
    assert p["round_started_at"].startswith("2026-11-30T10:00:01")


def test_no_current_round_after_30_days(db):
    for q in LIST:
        _ev(db, q, T0)
    _p(db, T0)  # 打满,发勋章
    p = _p(db, T0 + timedelta(days=31))
    assert p["checked"] == {} and p["round_started_at"] is None
    assert p["completed"] is False
    assert len(p["medals"]) == 1


def test_completion_writes_one_medal(db):
    _ev(db, "Q1", T0)
    _ev(db, "Q2", T0 + timedelta(hours=1))
    _ev(db, "Q3", T0 + timedelta(hours=2))
    _ev(db, "Q1", T0 + timedelta(hours=3))  # 补齐之后再拍,不改完成时刻
    now = T0 + timedelta(hours=4)
    p = _p(db, now)
    assert p["completed"] is True
    assert p["medals"] == [{"completed_at": "2026-10-01T12:00:00+00:00", "count": 3}]
    _p(db, now)
    _p(db, now)
    assert db.query(MustSeeMedal).count() == 1


def test_concurrent_duplicate_insert_does_not_raise(db, monkeypatch):
    """另一个请求抢先写了同一枚(唯一约束):本请求回滚后照常返回。"""
    from app.services import must_see_checkin as svc

    for q in LIST:
        _ev(db, q, T0)
    real = svc._medals

    def stale(db_, user_id, slug):  # 模拟读的时候还没看到对方那一行
        rows = real(db_, user_id, slug)
        if not getattr(stale, "done", False):
            stale.done = True
            db_.add(
                MustSeeMedal(
                    user_id=user_id, museum_slug=slug, completed_at=T0, count=3
                )
            )
            db_.commit()
            return []
        return rows

    monkeypatch.setattr(svc, "_medals", stale)
    p = _p(db, T0)
    assert p["completed"] is True
    assert db.query(MustSeeMedal).count() == 1


def test_medal_survives_footprint_delete_and_list_change(db, monkeypatch):
    for q in LIST:
        _ev(db, q, T0)
    _p(db, T0)
    # 删足迹 = user_id 置 NULL
    row = db.query(RecognitionEvent).filter_by(top_qid="Q2").one()
    row.user_id = None
    db.commit()
    p = _p(db, T0 + timedelta(hours=1))
    assert p["completed"] is False and len(p["medals"]) == 1
    # 清单加一件 → 本轮不再算完成;补拍那件也不发第二枚(本轮已有勋章)
    monkeypatch.setitem(must_see.MUST_SEE, "x", LIST + ["Q4"])
    _ev(db, "Q2", T0 + timedelta(hours=2))
    _ev(db, "Q4", T0 + timedelta(hours=3))
    p = _p(db, T0 + timedelta(hours=4))
    assert p["completed"] is True
    assert len(p["medals"]) == 1


def test_missed_completion_backfilled(db):
    for q in LIST:
        _ev(db, q, T0)
    p = _p(db, T0 + timedelta(days=31))  # 打满后从没打开过必看页
    assert p["medals"] == [{"completed_at": "2026-10-01T10:00:00+00:00", "count": 3}]


def test_empty_list_never_completes(db, monkeypatch):
    monkeypatch.setitem(must_see.MUST_SEE, "x", [])
    _ev(db, "Q1", T0)
    p = _p(db, T0)
    assert p["completed"] is False and p["medals"] == []
    assert db.query(MustSeeMedal).count() == 0


def test_anonymous_gets_empty_progress(db):
    _ev(db, "Q1", T0)
    assert progress(db, None, "x", now=T0) == {
        "checked": {},
        "round_started_at": None,
        "completed": False,
        "medals": [],
    }


def test_times_are_utc_aware(db):
    _ev(db, "Q1", T0)
    p = _p(db, T0)
    assert p["checked"]["Q1"].endswith("+00:00")
    assert p["round_started_at"].endswith("+00:00")
