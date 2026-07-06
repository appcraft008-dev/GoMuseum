"""guide 音频懒生成(点播放触发):有 audio_key 秒返,否则生成+落库+返 URL。仅 guide(Phase1)。"""

import asyncio

from app.services.content_repo import get_section_audio_key, persist_section_audio
from app.services.storage import get_object_storage


def _synth(text: str, language: str) -> bytes:
    """调 TTSService(async)→bytes。测试打桩此处。"""
    from app.services.tts_service import TTSService

    async def _run():
        return (await TTSService().generate_audio(text, language))["audio_data"]

    return asyncio.run(_run())


def get_or_make_audio_url(
    db, slug: str, qid: str, language: str, section: str = "guide"
):
    """返 (url, status)。status: ok|no_text。仅 guide(Phase1)。"""
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
    audio = _synth(body, language)  # 失败上抛 → 端点 503,不写 key
    new_key = persist_section_audio(db, qid, language, section, audio, storage)
    return storage.public_url(new_key), "ok"
