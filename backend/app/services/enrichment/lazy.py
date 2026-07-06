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


def lock_active(obj: MuseumObject) -> bool:
    """活锁 = 正在懒生成/懒翻译(端点 generating 字段的信号源;过期/坏时间戳=死锁不算)。"""
    at = (obj.attributes or {}).get("lazy_lock_at")
    if not at:
        return False
    try:
        return datetime.now(timezone.utc) - datetime.fromisoformat(at) < _LOCK_TTL
    except ValueError:
        return False  # 坏时间戳当过期


def try_acquire_lock(db, obj: MuseumObject, require_status=("stub",)) -> bool:
    """状态匹配且无活锁 → 落锁返回 True。乐观读写:竞态窗口极小,撞了最多浪费一次生成费。
    stub=懒生成入口;ready=懒翻译入口(该语言缺)。"""
    if obj.content_status not in require_status:
        return False
    if lock_active(obj):
        return False
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


def _generate(db, qid: str, language: str | None = None) -> dict:
    """真实生成:组件工厂装配 + generate_object(置 ready/empty)。测试 monkeypatch 此处。
    language=触发者的请求语言 → lang_priority(排队首,最快看到自己的语言)。"""
    from app.services.enrichment.factory import build_generation_components
    from app.services.enrichment.pipeline import generate_object

    o = db.query(MuseumObject).filter_by(qid=qid).one()
    from app.models.museum import Museum

    m = db.query(Museum).filter_by(id=o.museum_id).one()
    c = build_generation_components(m.slug)
    _req = [language] if language and language != "en" else []
    return generate_object(
        db,
        qid,
        enricher=c["enricher"],
        gate=c["gate"],
        translator=c["translator"],
        target_langs=["en"] + _req,  # 英语轴心 + 请求语言(仅);其余走懒翻译
        model="gpt-4o-mini",
        qa_suggester=c["qa_suggester"],
        registry=c["registry"],
        country_lang=c["country_lang"],
        lang_priority=language,
    )


def _translate(db, qid: str, language: str) -> dict:
    """懒翻译本体:单件单语言从 en 段纯翻译(补语种原语)。测试 monkeypatch 此处。"""
    from app.services.enrichment.backfill import translate_object_language
    from app.services.enrichment.content_enricher import default_complete
    from app.services.enrichment.translator import ContentTranslator

    o = db.query(MuseumObject).filter_by(qid=qid).one()
    out = translate_object_language(
        db,
        o,
        language,
        ContentTranslator(
            default_complete,
            complete_strong=lambda s, u: default_complete(s, u, model="gpt-4o"),
        ),
    )
    db.commit()
    return out


def _run_locked(
    qid: str, work, label: str, *, session_factory=None, close=True
) -> None:
    """后台任务骨架:限并发跑 work(db),完成/失败均清锁(失败允许下次重试)。"""
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
                out = work(db)
                logger.info("%s done: %s -> %s", label, qid, out)
            except Exception:
                db.rollback()
                logger.exception("%s failed: %s", label, qid)
            o = db.query(MuseumObject).filter_by(qid=qid).one_or_none()
            if o:
                _clear_lock(db, o)
        finally:
            if close:
                db.close()
    finally:
        _SEM.release()


def run_lazy_generation(
    qid: str, language: str | None = None, *, session_factory=None, close=True
) -> None:
    """stub 首访 → 生成英语轴心 + 请求语言(省成本;其余语言走 run_lazy_translation)。"""
    _run_locked(
        qid,
        lambda db: _generate(db, qid, language),
        "lazy generation",
        session_factory=session_factory,
        close=close,
    )


def run_lazy_translation(
    qid: str, language: str, *, session_factory=None, close=True
) -> None:
    """ready 但请求语言缺 → 只翻这一门语言(数十秒,费用分钱级)。"""
    _run_locked(
        qid,
        lambda db: _translate(db, qid, language),
        "lazy translation",
        session_factory=session_factory,
        close=close,
    )


def run_lazy_images(qid: str, *, session_factory=None, close=True) -> None:
    """懒补漏(spec 图像自存):单件物化缺图。不占内容锁——图物化与内容生成可并行,
    撞了最多重复下载一张(幂等)。批量预物化为主,此钩子只兜运维疏漏/新进目录。"""
    if session_factory is None:
        from app.core.database import SessionLocal

        session_factory = SessionLocal
    db = session_factory()
    try:
        o = db.query(MuseumObject).filter_by(qid=qid).one_or_none()
        if o is not None:
            from app.services.enrichment.materializer import (
                materialize_object_images,
            )

            out = materialize_object_images(db, o)
            db.commit()
            logger.info("lazy images done: %s -> %s", qid, out)
    except Exception:
        db.rollback()
        logger.exception("lazy images failed: %s", qid)
    finally:
        if close:
            db.close()


def _has_missing_images(db, object_id) -> bool:
    from app.models.museum_object import ObjectImage

    return (
        db.query(ObjectImage)
        .filter(
            ObjectImage.object_id == object_id,
            ObjectImage.image_key.is_(None),
            ObjectImage.source_url.isnot(None),
        )
        .first()
        is not None
    )


def _has_published(db, object_id, lang) -> bool:
    from app.models.content import ObjectContentSection

    return (
        db.query(ObjectContentSection)
        .filter(
            ObjectContentSection.object_id == object_id,
            ObjectContentSection.language == lang,
            ObjectContentSection.status == "published",
            ObjectContentSection.body.isnot(None),
        )
        .first()
        is not None
    )


def _has_any_section(db, object_id, lang) -> bool:
    """该语言有任何段落(含 needs_review)= 已尝试过翻译。用于防死循环重触发。"""
    from app.models.content import ObjectContentSection

    return (
        db.query(ObjectContentSection)
        .filter(
            ObjectContentSection.object_id == object_id,
            ObjectContentSection.language == lang,
        )
        .first()
        is not None
    )


def maybe_trigger(db, qid: str, *, schedule, environment=None, language=None) -> None:
    """content 端点接线(拿到锁才调度,其余静默):
    - stub → 懒生成(完整生成,请求语言优先);
    - ready 但请求语言缺已发布内容且有 en 轴心 → 懒翻译(只翻该语言);
    - empty 不动(无可接地材料,防循环烧钱)。
    只在部署环境生效(development/测试不触发:防误连库、误烧 LLM 费)。"""
    if environment is None:
        from app.core.config import settings

        environment = settings.ENVIRONMENT
    if environment not in ("staging", "production"):
        return
    o = db.query(MuseumObject).filter_by(qid=qid).one_or_none()
    if o is None:
        return
    if _has_missing_images(db, o.id):  # 懒补漏:缺图顺手补(独立于内容动作)
        schedule(run_lazy_images, qid)
    if o.content_status == "stub":
        if try_acquire_lock(db, o):
            schedule(run_lazy_generation, qid, language)
        return
    if (
        o.content_status == "ready"
        and language
        and language != "en"
        and not _has_any_section(db, o.id, language)
        and _has_published(db, o.id, "en")
    ):
        if try_acquire_lock(db, o, require_status=("ready",)):
            schedule(run_lazy_translation, qid, language)
