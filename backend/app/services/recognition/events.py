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
    user_id=None,
) -> None:
    """记一次识别事件。独立小事务,失败回滚不影响主流程。

    user_id 只在令牌解析成功时有值,它同时是足迹页的数据源(见 /history/*)。
    仍然沿用"埋点失败不打断识别"的纪律 —— 足迹丢一条,好过识别 500。"""
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
                user_id=user_id,
            )
        )
        db.commit()
    except Exception:
        logger.exception("record_event failed")
        try:
            db.rollback()
        except Exception:
            pass


def confirm_event(db, phash: str, qid: str) -> bool:
    """回填最近 24h 内该 phash 最新一条事件的 confirmed_qid。
    qid 须存在于目录否则忽略;无匹配事件也静默返回(fire-and-forget)。

    返回 **这次识别此前从未被确认过** —— 候选态的计费幂等就靠它
    (见 recognize_confirm):一次拍照只扣一次,用户点完候选 A 回去再点 B
    不该再扣一次(候选恰恰是"没把握"的那一档,点错很常见)。

    判据取"24h 内该 phash 有没有任何一行已确认",不是"最新那行确认没有":
    同一张照片重拍会命中识别缓存、再落一行新事件,只看最新行会把它当首次确认,
    于是同一张图反复拍就能反复扣 —— 而缓存命中本来就是不扣的。
    任何异常一律 False(不扣):扣不到好过错扣。"""
    try:
        from app.models.museum_object import MuseumObject

        if not db.query(MuseumObject).filter_by(qid=qid).first():
            return False
        cutoff = datetime.utcnow() - timedelta(hours=24)
        rows = (
            db.query(RecognitionEvent)
            .filter(
                RecognitionEvent.phash == phash,
                RecognitionEvent.created_at >= cutoff,
            )
            .order_by(RecognitionEvent.created_at.desc())
            .all()
        )
        if not rows:
            return False
        first_time = not any(r.confirmed_qid for r in rows)
        rows[0].confirmed_qid = qid
        db.commit()
        return first_time
    except Exception:
        logger.exception("confirm_event failed")
        try:
            db.rollback()
        except Exception:
            pass
        return False
