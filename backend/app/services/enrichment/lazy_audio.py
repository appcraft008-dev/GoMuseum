"""guide 音频懒生成(点播放触发):有 audio_key 秒返,否则生成+落库+返 URL。仅 guide(Phase1)。"""

import asyncio
from datetime import datetime, timedelta, timezone

from app.services.content_repo import get_section_audio_key, persist_section_audio
from app.services.storage import get_object_storage

# 段级音频锁 TTL(音频生成快;短 TTL 防死锁残留)。复用懒锁思路,存对象 attributes。
_AUDIO_LOCK_TTL = timedelta(minutes=2)


def _synth(text: str, language: str) -> bytes:
    """调 TTSService(async)→bytes。测试打桩此处。"""
    from app.services.tts_service import TTSService

    async def _run():
        return (await TTSService().generate_audio(text, language))["audio_data"]

    return asyncio.run(_run())


def _audio_lock_active(obj, lang: str, section: str) -> bool:
    at = ((obj.attributes or {}).get("audio_locks") or {}).get(f"{lang}:{section}")
    if not at:
        return False
    try:
        return datetime.now(timezone.utc) - datetime.fromisoformat(at) < _AUDIO_LOCK_TTL
    except ValueError:
        return False  # 坏时间戳当过期


def _set_audio_lock(db, obj, lang: str, section: str, on: bool) -> None:
    # ponytail: 与 lazy_lock_at 共用 attributes JSON,并发读改写=后写覆盖;
    # 2min TTL 自愈,可接受。若音频并发成热点,改 Redis/独立列。
    locks = dict((obj.attributes or {}).get("audio_locks") or {})
    k = f"{lang}:{section}"
    if on:
        locks[k] = datetime.now(timezone.utc).isoformat()
    else:
        locks.pop(k, None)
    obj.attributes = {**(obj.attributes or {}), "audio_locks": locks}
    db.commit()


def get_or_make_audio_url(
    db, slug: str, qid: str, language: str, section: str = "guide"
):
    """返 (url, status)。status: ok|no_text|busy。guide+深度模块通用(按 section 取已发布正文)。
    段级锁:同段同语言并发点播放时,只一个真生成,其余得 busy(前端稍候自动重试)。"""
    from app.models.content import ObjectContentSection
    from app.models.museum_object import MuseumObject

    storage = get_object_storage()
    key = get_section_audio_key(db, qid, language, section)
    if key:
        return storage.public_url(key), "ok"
    obj = db.query(MuseumObject).filter_by(qid=qid).one_or_none()
    if obj is None:
        return None, "no_text"
    # 按 section 取该语言已发布正文(guide 与深度模块统一)
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
        return None, "no_text"
    if _audio_lock_active(obj, language, section):
        return None, "busy"  # 另一请求正在生成同段音频
    _set_audio_lock(db, obj, language, section, True)
    try:
        audio = _synth(body, language)  # 失败上抛 → 端点 503,不写 key
        new_key = persist_section_audio(db, qid, language, section, audio, storage)
    finally:
        _set_audio_lock(db, obj, language, section, False)
    return storage.public_url(new_key), "ok"


def get_or_make_qa_audio_url(db, qid: str, language: str, qa_sort: int):
    """问答音频(问+答连念):audio_key 落 QA 行;key 按 (qid,lang,sort)。返 (url,status)。"""
    from app.models.content import ObjectSuggestedQuestion
    from app.models.museum_object import MuseumObject

    storage = get_object_storage()
    obj = db.query(MuseumObject).filter_by(qid=qid).one_or_none()
    if obj is None:
        return None, "no_text"
    row = (
        db.query(ObjectSuggestedQuestion)
        .filter_by(
            object_id=obj.id, language=language, sort=qa_sort, status="published"
        )
        .one_or_none()
    )
    if row is None:
        return None, "no_text"
    if row.audio_key:
        return storage.public_url(row.audio_key), "ok"
    section = f"qa:{qa_sort}"
    if _audio_lock_active(obj, language, section):
        return None, "busy"
    _set_audio_lock(db, obj, language, section, True)
    try:
        text = f"{row.question}\n\n{row.answer}"  # 问+答连念(闭眼听需上下文)
        audio = _synth(text, language)
        key = f"object-audio/{qid}/{language}/qa_{qa_sort}.mp3"
        storage.put(key, audio, "audio/mpeg")  # put 成功才写 key
        row.audio_key = key
        db.commit()
    finally:
        _set_audio_lock(db, obj, language, section, False)
    return storage.public_url(key), "ok"


def get_or_make_artist_bio_audio_url(db, qid: str, language: str):
    """作者介绍音频:按作者共享一份(key 按 artist qid;同作者所有作品复用)。返 (url,status)。"""
    from app.models.artist import Artist
    from app.models.museum_object import MuseumObject

    storage = get_object_storage()
    obj = db.query(MuseumObject).filter_by(qid=qid).one_or_none()
    aqid = ((obj.attributes or {}) if obj else {}).get("artist_qid")
    art = db.query(Artist).filter_by(qid=aqid).first() if aqid else None
    if art is None:
        return None, "no_text"
    existing = (art.bio_audio or {}).get(language)
    if existing:
        return storage.public_url(existing), "ok"
    text = (art.bio or {}).get(language)
    if not text:
        return None, "no_text"
    section = "artist_bio"
    if _audio_lock_active(obj, language, section):
        return None, "busy"
    _set_audio_lock(db, obj, language, section, True)
    try:
        audio = _synth(text, language)
        key = f"object-audio/artist/{aqid}/{language}.mp3"
        storage.put(key, audio, "audio/mpeg")  # put 成功才写 key
        art.bio_audio = {**(art.bio_audio or {}), language: key}
        db.commit()
    finally:
        _set_audio_lock(db, obj, language, section, False)
    return storage.public_url(key), "ok"
