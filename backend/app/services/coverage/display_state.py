"""展陈状态汇总:识别流量证据(强,动态)+ Wikidata P276 静态先验(弱)→ attributes["display"]。
spec ③: 近 traffic_days 天有 match/confirmed 识别事件 → CONFIRMED;否则 p276 或已有
location_claim 证据 → LIKELY;否则 UNKNOWN。evidence 数组按 (source, type) 追加去重，
不清空其它适配器（如 Joconde）写入的证据。"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import and_, or_
from sqlalchemy.orm import Session

from app.models.museum import Museum
from app.models.museum_object import MuseumObject
from app.models.recognition_event import RecognitionEvent

STATUS = (
    "CONFIRMED_ON_DISPLAY",
    "LIKELY_ON_DISPLAY",
    "TEMPORARY_EXHIBITION",
    "NOT_ON_DISPLAY",
    "UNKNOWN",
)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _dedupe_append(evidence: list[dict], entry: dict) -> list[dict]:
    """同 (source, type) 只留最新一条;其它来源原样保留。"""
    kept = [
        e
        for e in evidence
        if not (e.get("source") == entry["source"] and e.get("type") == entry["type"])
    ]
    kept.append(entry)
    return kept


def add_evidence(
    obj: MuseumObject,
    *,
    source: str,
    type: str,
    detail: str | None = None,
    location: str | None = None,
    confidence: float | None = None,
) -> None:
    """纯函数：往 obj.attributes["display"]["evidence"] 追加证据（去重），
    更新 location/confidence/verified_at。不设置 status——status 是 recompute_display 的职责。"""
    attrs = obj.attributes or {}
    display = dict(attrs.get("display") or {})
    entry = {"source": source, "type": type, "at": _now_iso()}
    if detail is not None:
        entry["detail"] = detail
    display["evidence"] = _dedupe_append(list(display.get("evidence") or []), entry)
    if location is not None:
        display["location"] = location
    if confidence is not None:
        display["confidence"] = confidence
    display["verified_at"] = _now_iso()
    # MutableDict 对嵌套 mutation 不追踪脏标记，整键重赋值才能让 SQLAlchemy 检测到变化
    obj.attributes = {**attrs, "display": display}


def recompute_display(db: Session, museum_slug: str, *, traffic_days: int = 30) -> dict:
    """重算该馆全部对象的 attributes["display"]。返回 {"confirmed","likely","unknown"} 计数。"""
    museum = db.query(Museum).filter_by(slug=museum_slug).one_or_none()
    if museum is None:
        return {"confirmed": 0, "likely": 0, "unknown": 0}

    since = datetime.utcnow() - timedelta(days=traffic_days)
    counts = {"confirmed": 0, "likely": 0, "unknown": 0}

    for obj in db.query(MuseumObject).filter_by(museum_id=museum.id).all():
        attrs = obj.attributes or {}
        display = dict(attrs.get("display") or {})
        evidence = list(display.get("evidence") or [])

        n_scans = 0
        if obj.qid:
            n_scans = (
                db.query(RecognitionEvent)
                .filter(
                    RecognitionEvent.created_at >= since,
                    or_(
                        and_(
                            RecognitionEvent.outcome == "match",
                            RecognitionEvent.top_qid == obj.qid,
                        ),
                        RecognitionEvent.confirmed_qid == obj.qid,
                    ),
                )
                .count()
            )

        if n_scans:
            evidence = _dedupe_append(
                evidence,
                {
                    "source": "recognition_traffic",
                    "type": "confirmed_scan",
                    "at": _now_iso(),
                    "detail": f"n={n_scans}",
                },
            )
            display["status"] = "CONFIRMED_ON_DISPLAY"
            counts["confirmed"] += 1
        elif attrs.get("p276"):
            evidence = _dedupe_append(
                evidence,
                {
                    "source": "wikidata_p276",
                    "type": "location_claim",
                    "at": _now_iso(),
                    "detail": str(attrs["p276"]),
                },
            )
            display["status"] = "LIKELY_ON_DISPLAY"
            counts["likely"] += 1
        elif any(e.get("type") == "location_claim" for e in evidence):
            display["status"] = "LIKELY_ON_DISPLAY"
            counts["likely"] += 1
        else:
            display["status"] = "UNKNOWN"
            counts["unknown"] += 1

        display["evidence"] = evidence
        display["verified_at"] = _now_iso()
        obj.attributes = {**attrs, "display": display}
        db.add(obj)

    db.commit()
    return counts
