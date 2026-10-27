"""必看打卡:从识别事件现算打卡与轮,打满一轮落一枚勋章(spec 2026-10-27 §五.2-3)。

打卡 = 该用户、快门现场拍(capture='camera')、不是搜索确认、足迹判据认定的那件
在该馆必看清单里。**不看 museum_slug**:App 走全局识别端点,事件行这一列是 NULL。
相邻两次打卡间隔 > 30 天切成新一轮。单用户单馆的打卡量很小,取出来在 Python 里切。
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError

from app.api.v1.endpoints.history import _footprint_qid
from app.models.must_see_medal import MustSeeMedal
from app.models.recognition_event import RecognitionEvent
from app.services import must_see

ROUND_GAP = timedelta(days=30)


def _iso(dt: datetime) -> str:
    return dt.replace(tzinfo=timezone.utc).isoformat()


def checkins(db, user_id: str, slug: str) -> list[tuple[str, datetime]]:
    listed = set(must_see.MUST_SEE.get(slug) or [])
    if not listed:
        return []
    E = RecognitionEvent
    rows = (
        db.query(E)
        .filter(
            E.user_id == user_id,
            E.capture == "camera",
            or_(E.confirm_source.is_(None), E.confirm_source != "search"),
        )
        .order_by(E.created_at)
        .all()
    )
    out = []
    for ev in rows:
        q = _footprint_qid(ev)
        if q in listed:
            out.append((q, ev.created_at))
    return out


def split_rounds(cks: list[tuple[str, datetime]]) -> list[list[tuple[str, datetime]]]:
    rounds: list[list[tuple[str, datetime]]] = []
    for c in cks:
        if rounds and c[1] - rounds[-1][-1][1] <= ROUND_GAP:
            rounds[-1].append(c)
        else:
            rounds.append([c])
    return rounds


def current_round(cks, now: datetime) -> list[tuple[str, datetime]]:
    rounds = split_rounds(cks)
    if not rounds or now - rounds[-1][-1][1] > ROUND_GAP:
        return []
    return rounds[-1]


def _completed_at(rnd, listed: set[str]) -> datetime | None:
    """这一轮补齐清单最后一件的那次打卡时间;没补齐 → None。"""
    if not listed:
        return None
    seen: set[str] = set()
    for q, at in rnd:
        seen.add(q)
        if listed <= seen:
            return at
    return None


def _medals(db, user_id: str, slug: str) -> list[MustSeeMedal]:
    return (
        db.query(MustSeeMedal)
        .filter_by(user_id=user_id, museum_slug=slug)
        .order_by(MustSeeMedal.completed_at.desc())
        .all()
    )


def progress(db, user_id: str | None, slug: str, now: datetime | None = None) -> dict:
    empty = {"checked": {}, "round_started_at": None, "completed": False, "medals": []}
    if not user_id:
        return empty
    now = now or datetime.utcnow()
    listed = set(must_see.MUST_SEE.get(slug) or [])
    cks = checkins(db, user_id, slug)
    medals = _medals(db, user_id, slug)
    # 遍历所有轮补发:补齐那次的拉取失败、30 天内又没打开必看页,这一轮也不能漏发
    for rnd in split_rounds(cks):
        done_at = _completed_at(rnd, listed)
        if done_at is None:
            continue
        start, end = rnd[0][1], rnd[-1][1]
        if any(start <= m.completed_at <= end for m in medals):
            continue  # 一轮只发一枚
        db.add(
            MustSeeMedal(
                user_id=user_id,
                museum_slug=slug,
                completed_at=done_at,
                count=len(listed),
            )
        )
        try:
            db.commit()
        except IntegrityError:
            db.rollback()  # 并发的另一个请求已经写了同一枚
        medals = _medals(db, user_id, slug)

    cur = current_round(cks, now)
    checked: dict[str, str] = {}
    for q, at in cur:
        checked.setdefault(q, _iso(at))
    return {
        "checked": checked,
        "round_started_at": _iso(cur[0][1]) if cur else None,
        "completed": bool(cur) and _completed_at(cur, listed) is not None,
        "medals": [
            {"completed_at": _iso(m.completed_at), "count": m.count} for m in medals
        ],
    }
