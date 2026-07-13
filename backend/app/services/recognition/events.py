"""识别事件埋点(KPI + 展陈证据一表两吃):落一行 recognition_events;确认回填 confirmed_qid。

任何异常一律吞掉只记日志——埋点绝不能打断识别主流程。"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta

from app.models.recognition_event import RecognitionEvent

logger = logging.getLogger(__name__)


def record_event(
    db,
    *,
    museum_slug,
    phash,
    outcome,
    top_qid,
    top_score,
    language,
    engine,
) -> None:
    """记一次识别事件。独立小事务,失败回滚不影响主流程。"""
    try:
        db.add(
            RecognitionEvent(
                museum_slug=museum_slug,
                phash=phash,
                outcome=outcome,
                top_qid=top_qid,
                top_score=top_score,
                language=language,
                engine=engine,
            )
        )
        db.commit()
    except Exception:
        logger.exception("record_event failed")
        try:
            db.rollback()
        except Exception:
            pass


def confirm_event(db, phash: str, qid: str) -> None:
    """回填最近 24h 内该 phash 最新一条事件的 confirmed_qid。
    qid 须存在于目录否则忽略;无匹配事件也静默返回(fire-and-forget)。"""
    try:
        from app.models.museum_object import MuseumObject

        if not db.query(MuseumObject).filter_by(qid=qid).first():
            return
        cutoff = datetime.utcnow() - timedelta(hours=24)
        row = (
            db.query(RecognitionEvent)
            .filter(
                RecognitionEvent.phash == phash,
                RecognitionEvent.created_at >= cutoff,
            )
            .order_by(RecognitionEvent.created_at.desc())
            .first()
        )
        if row is None:
            return
        row.confirmed_qid = qid
        db.commit()
    except Exception:
        logger.exception("confirm_event failed")
        try:
            db.rollback()
        except Exception:
            pass
