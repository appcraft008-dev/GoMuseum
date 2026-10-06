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
    duration_ms=None,
    timings=None,
    text_trace=None,
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
                duration_ms=duration_ms,
                timings=timings,
                text_trace=text_trace,
            )
        )
        db.commit()
    except Exception:
        logger.exception("record_event failed")
        try:
            db.rollback()
        except Exception:
            pass


def confirm_event(db, phash: str, qid: str, source: str = "candidates") -> bool:
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
        prev = next((r.confirmed_qid for r in rows if r.confirmed_qid), None)
        # 「一次拍照只扣一次」只认计过费的确认:search 来源只记答案,不占这把锁(S4)
        first_time = not any(
            r.confirmed_qid and r.confirm_source != "search" for r in rows
        )
        # 选中的这件不能还挂在任何一行的 rejected 里(旧行上「都不是」过、重拍后选中它)
        for r in rows[1:]:
            if r.rejected_qids and qid in r.rejected_qids:
                r.rejected_qids = [q for q in r.rejected_qids if q != qid] or None
        row = rows[0]
        # S3 改选:上一次确认的那件就是「第一次选错」。服务端自己知道,不收客户端的 previous。
        rejected = [q for q in (row.rejected_qids or []) if q != qid]
        if prev and prev != qid and prev not in rejected:
            rejected.append(prev)
        row.rejected_qids = rejected or None
        row.confirmed_qid = qid
        row.confirm_source = source
        db.commit()
        return first_time
    except Exception:
        logger.exception("confirm_event failed")
        try:
            db.rollback()
        except Exception:
            pass
        return False


def reject_event(db, phash: str, qids: list[str]) -> None:
    """「都不是」:把这组候选并进最近 24h 该 phash 最新一条事件的 rejected_qids。
    无匹配事件静默返回;任何异常吞掉(fire-and-forget)。"""
    try:
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
        from app.models.museum_object import MuseumObject

        # 匿名可调:只收目录里真有的 qid(同 confirm_event),防垃圾数据污染分析
        known = {
            q for (q,) in db.query(MuseumObject.qid).filter(MuseumObject.qid.in_(qids))
        }
        merged = list(row.rejected_qids or [])
        merged += [q for q in qids if q in known and q not in merged]
        row.rejected_qids = merged
        db.commit()
    except Exception:
        logger.exception("reject_event failed")
        try:
            db.rollback()
        except Exception:
            pass
