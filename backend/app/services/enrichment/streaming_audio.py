"""TTS 流式播放 + 解耦落库(单次 tee)。

红线:**一次 TTS 调用**,输出流劈两路——客户端(边收边播)+ 累积buffer(整段完→R2)。
落库跑在 **detached task**,客户端中途断连不取消它 → R2 绝不存半截、生成不浪费(tts-1 按
字符已付费,抽完落库是成本最优)。第二个并发请求由段级锁挡成 409(前端重试→届时缓存命中)。
"""

from __future__ import annotations

import asyncio
import logging
from typing import AsyncIterator, Awaitable, Callable

logger = logging.getLogger(__name__)

# 持有 detached producer 引用,防被 GC(完成后自动移除)
_producers: set[asyncio.Task] = set()


async def start_and_stream(
    chunk_source: Callable[[], AsyncIterator[bytes]],
    persist: Callable[[bytes | None], Awaitable[None]],
) -> AsyncIterator[bytes]:
    """一次 tee。

    chunk_source(): 产 bytes 的 async 迭代器(**内部只调一次 TTS**)。
    persist(full|None): 整段成功→full bytes 落库;失败→None(释放锁不写key)。async。

    返回给客户端的 async generator;累积+落库在 detached task 里跑,**客户端断连也跑完**。
    """
    queue: asyncio.Queue = asyncio.Queue()

    async def _producer() -> None:
        acc: list[bytes] = []
        try:
            async for chunk in chunk_source():  # 唯一一次 TTS 调用
                acc.append(chunk)
                await queue.put(chunk)
            await persist(b"".join(acc))  # 整段完 → R2
        except Exception:  # 生成/落库失败:释放锁,不写 key
            logger.exception("streaming audio producer failed")
            try:
                await persist(None)
            except Exception:
                logger.exception("persist(None) cleanup failed")
        finally:
            await queue.put(None)  # 哨兵:通知客户端结束

    task = asyncio.create_task(_producer())
    _producers.add(task)
    task.add_done_callback(_producers.discard)

    async def _client() -> AsyncIterator[bytes]:
        # 只负责把 chunk 递给客户端;断连时本 gen 被取消,producer 仍继续 → 落库不中断
        while True:
            item = await queue.get()
            if item is None:
                break
            yield item

    return _client()


def _prepare_sync(qid: str, language: str, section: str) -> dict:
    """同步:缓存命中?取已发布正文?上段级锁。各用独立 session(不依赖请求生命周期)。
    status: cached|no_text|busy|ready。"""
    from app.core.database import SessionLocal
    from app.models.content import ObjectContentSection
    from app.models.museum_object import MuseumObject
    from app.services.content_repo import get_section_audio_key
    from app.services.enrichment.lazy_audio import (
        _audio_lock_active,
        _set_audio_lock,
    )
    from app.services.storage import get_object_storage

    db = SessionLocal()
    try:
        key = get_section_audio_key(db, qid, language, section)
        if key:
            return {"status": "cached", "url": get_object_storage().public_url(key)}
        obj = db.query(MuseumObject).filter_by(qid=qid).one_or_none()
        if obj is None:
            return {"status": "no_text"}
        row = (
            db.query(ObjectContentSection)
            .filter_by(
                object_id=obj.id,
                language=language,
                section_code=section,
                status="published",
            )
            .one_or_none()
        )
        body = row.body if row else None
        if not body:
            return {"status": "no_text"}
        if _audio_lock_active(obj, language, section):
            return {"status": "busy"}
        _set_audio_lock(db, obj, language, section, True)
        db.commit()
        return {"status": "ready", "body": body}
    finally:
        db.close()


def _persist_sync(qid: str, language: str, section: str, full: bytes | None) -> None:
    """同步:整段成功→R2+audio_key;无论成败→释放段级锁。独立 session。"""
    from app.core.database import SessionLocal
    from app.models.museum_object import MuseumObject
    from app.services.content_repo import persist_section_audio
    from app.services.enrichment.lazy_audio import _set_audio_lock
    from app.services.storage import get_object_storage

    db = SessionLocal()
    try:
        obj = db.query(MuseumObject).filter_by(qid=qid).one_or_none()
        try:
            if full is not None and obj is not None:
                persist_section_audio(
                    db, qid, language, section, full, get_object_storage()
                )
        finally:
            if obj is not None:
                _set_audio_lock(db, obj, language, section, False)
                db.commit()
    finally:
        db.close()


async def stream_section_audio(qid: str, language: str, section: str):
    """返 (status, payload)。status: cached(url)|no_text|busy|stream(async gen)。
    stream:一次 TTS 调用边播边落库(解耦扛断连)。"""
    prep = await asyncio.to_thread(_prepare_sync, qid, language, section)
    status = prep["status"]
    if status != "ready":
        return status, prep.get("url")

    from app.services.tts_service import TTSService

    body = prep["body"]
    tts = TTSService()

    def chunk_source() -> AsyncIterator[bytes]:
        return tts.generate_audio_stream(body, language)  # 唯一一次 TTS 调用

    async def persist(full: bytes | None) -> None:
        await asyncio.to_thread(_persist_sync, qid, language, section, full)

    gen = await start_and_stream(chunk_source, persist)
    return "stream", gen
