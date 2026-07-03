"""懒生成(路线图3c):stub 首次访问触发后台生成一次。
锁=attributes.lazy_lock_at(TTL 自愈);并发上限=进程级信号量;完成/失败均清锁。
不对外暴露中间状态——stub 期间前端照旧"待完善",生成完刷新即 ready(契约形状零变化)。
plan 2026-07-03-lazy-generation。"""

from __future__ import annotations

import logging
import threading
from datetime import datetime, timedelta, timezone

from app.models.museum_object import MuseumObject

logger = logging.getLogger(__name__)

_LOCK_TTL = timedelta(minutes=10)  # 崩溃自愈:超时视为死锁可重拿
# ponytail: 进程级并发上限2,保护 API 响应与 LLM 限速;多 worker/量大再上队列
_SEM = threading.Semaphore(2)


def try_acquire_lock(db, obj: MuseumObject) -> bool:
    """stub 且无活锁 → 落锁返回 True。乐观读写:竞态窗口极小,撞了最多浪费一次生成费。"""
    if obj.content_status != "stub":
        return False
    at = (obj.attributes or {}).get("lazy_lock_at")
    if at:
        try:
            if datetime.now(timezone.utc) - datetime.fromisoformat(at) < _LOCK_TTL:
                return False
        except ValueError:
            pass  # 坏时间戳当过期
    obj.attributes = {
        **(obj.attributes or {}),
        "lazy_lock_at": datetime.now(timezone.utc).isoformat(),
    }
    db.commit()
    return True


def _clear_lock(db, obj: MuseumObject) -> None:
    attrs = dict(obj.attributes or {})
    attrs.pop("lazy_lock_at", None)
    obj.attributes = attrs
    db.commit()


def _generate(db, qid: str) -> dict:
    """真实生成:组件工厂装配 + generate_object(置 ready/empty)。测试 monkeypatch 此处。"""
    from app.services.enrichment.factory import build_generation_components
    from app.services.enrichment.pipeline import generate_object

    o = db.query(MuseumObject).filter_by(qid=qid).one()
    from app.models.museum import Museum

    m = db.query(Museum).filter_by(id=o.museum_id).one()
    c = build_generation_components(m.slug)
    return generate_object(
        db,
        qid,
        enricher=c["enricher"],
        gate=c["gate"],
        translator=c["translator"],
        target_langs=c["target_langs"],
        model="gpt-4o-mini",
        qa_suggester=c["qa_suggester"],
        registry=c["registry"],
        country_lang=c["country_lang"],
    )


def run_lazy_generation(qid: str, *, session_factory=None, close=True) -> None:
    """后台任务体:限并发跑生成,完成/失败均清锁(失败留 stub 允许下次重试)。"""
    if session_factory is None:
        from app.core.database import SessionLocal

        session_factory = SessionLocal
    if not _SEM.acquire(blocking=False):
        # 并发满:放弃本次并清锁,下次访问重触发
        db = session_factory()
        try:
            o = db.query(MuseumObject).filter_by(qid=qid).one_or_none()
            if o:
                _clear_lock(db, o)
        finally:
            if close:
                db.close()
        return
    try:
        db = session_factory()
        try:
            try:
                out = _generate(db, qid)
                logger.info("lazy generation done: %s -> %s", qid, out)
            except Exception:
                db.rollback()
                logger.exception("lazy generation failed: %s", qid)
            o = db.query(MuseumObject).filter_by(qid=qid).one_or_none()
            if o:
                _clear_lock(db, o)
        finally:
            if close:
                db.close()
    finally:
        _SEM.release()


def maybe_trigger(db, qid: str, *, schedule, environment=None) -> None:
    """content 端点接线:stub 且拿到锁 → schedule(run_lazy_generation, qid)。其余静默。
    只在部署环境生效(development/测试不触发:防误连库、误烧 LLM 费)。"""
    if environment is None:
        from app.core.config import settings

        environment = settings.ENVIRONMENT
    if environment not in ("staging", "production"):
        return
    o = db.query(MuseumObject).filter_by(qid=qid).one_or_none()
    if o is None:
        return
    if try_acquire_lock(db, o):
        schedule(run_lazy_generation, qid)
