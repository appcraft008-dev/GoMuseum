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
    """返 (url, status)。status: ok|no_text|busy。仅 guide(Phase1)。
    段级锁:同段同语言并发点播放时,只一个真生成,其余得 busy(前端可稍后重试)。"""
    from app.models.museum_object import MuseumObject
    from app.services.museum_repo import get_object_content

    storage = get_object_storage()
    key = get_section_audio_key(db, qid, language, section)
    if key:
        return storage.public_url(key), "ok"
    # 取该语言 guide 正文(已发布才有)
    data = get_object_content(db, slug, qid, language)
    if data is None:
        return None, "no_text"
    body = (data.get("default_guide") or {}).get("body")
    if not body:
        return None, "no_text"
    obj = db.query(MuseumObject).filter_by(qid=qid).one_or_none()
    if obj is None:
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
