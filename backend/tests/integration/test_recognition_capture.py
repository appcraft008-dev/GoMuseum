"""识别带「拍照/相册」(capture)与「没扣成费就撤销」(spec 2026-10-27 必看打卡 §五.1-2)。

打卡只认 capture='camera' 的行;命中后没扣成费(402/扣费链路抛错)、或等来的是
在途首请求的结果(扣费归首请求),这一行的 capture 必须清成 NULL。
"""

import pytest

from app.models.recognition_event import RecognitionEvent
from tests.integration.test_pass_scope_by_museum import (  # noqa: F401  db 是 fixture
    _ben,
    _jpeg,
    _Redis,
    _ticket,
    db,
)


def _recognize(db, hit_qid, *, capture, uid="u", redis=None, vector_top=0.95):
    from app.services.recognition.service import recognize_billed

    return recognize_billed(
        db,
        None,
        _jpeg(),
        user_id=uid,
        device_id=None,
        redis=redis or _Redis(),
        embed_fn=lambda b: "V",
        vector_query_fn=lambda db, v, mid: [(hit_qid, vector_top)],
        capture=capture,
    )


def _rows(db):
    db.expire_all()
    return db.query(RecognitionEvent).order_by(RecognitionEvent.created_at).all()


def test_capture_recorded_on_event(db):
    _ben(db, "u", quota=5)
    _recognize(db, "Q1", capture="camera")
    _recognize(db, "Q1", capture=None)
    caps = sorted((r.capture or "-") for r in _rows(db))
    assert caps == ["-", "camera"]


def test_event_id_not_leaked_to_response(db):
    _ben(db, "u", quota=5)
    out = _recognize(db, "Q1", capture="camera")
    assert "_event_id" not in out


def test_402_after_match_clears_capture(db):
    from app.services.recognition.service import QuotaExceededError

    _ben(db, "u", quota=0)
    _ticket(db, "u", "paris_pass_7d")  # 别处的票:前置闸放行,命中荷兰后 402
    with pytest.raises(QuotaExceededError):
        _recognize(db, "Q9", capture="camera")
    (row,) = _rows(db)
    assert row.outcome == "match"
    assert row.capture is None, "没扣成费的命中不能留 camera(否则白盖章)"


def test_billing_exception_after_match_clears_capture(db, monkeypatch):
    from app.services import entitlement_service as es

    _ben(db, "u", quota=5)

    def boom(*a, **k):
        raise RuntimeError("db down")

    monkeypatch.setattr(es, "museum_of_qid", boom)
    with pytest.raises(RuntimeError):
        _recognize(db, "Q1", capture="camera")
    (row,) = _rows(db)
    assert row.capture is None


def test_inflight_waiter_row_has_no_capture(db, monkeypatch):
    """等来的是在途首请求的结果:扣费归首请求那一行,等待方这行不算打卡。"""
    import json

    from app.services.recognition import service

    _ben(db, "u", quota=5)
    first = _recognize(db, "Q1", capture="camera")
    first.pop("photo_feedback", None)

    calls = {"n": 0}

    def fake_wait(redis, ckey):
        calls["n"] += 1
        return json.dumps(first)

    class _Busy(_Redis):
        def set(self, *a, **k):
            return False  # 锁被首请求占着 → 走等待

    monkeypatch.setattr(service, "_wait_inflight", fake_wait)
    _recognize(db, "Q1", capture="camera", redis=_Busy())
    assert calls["n"] == 1
    rows = _rows(db)
    assert [r.capture for r in rows] == ["camera", None]
