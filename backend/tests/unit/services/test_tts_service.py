import asyncio

from app.services import tts_service as tts_mod
from app.services.tts_service import TTSService


class _FakeResponse:
    """复刻 openai 2.x：iter_bytes() 是同步生成器（不能 async for）。"""

    def iter_bytes(self, chunk_size=8192):
        yield b"AB"
        yield b"CD"


class _FakeSpeech:
    async def create(self, **kwargs):
        return _FakeResponse()


class _FakeClient:
    class audio:  # noqa: N801
        speech = _FakeSpeech()


def test_generate_audio_reads_sync_iter_bytes(monkeypatch):
    # 回归：openai 2.x 下 iter_bytes() 同步，旧代码用 async for 抛
    # "'async for' requires an object with __aiter__ method, got generator" → 音频端点 500。
    monkeypatch.setattr(tts_mod, "_get_openai_client", lambda: _FakeClient())
    result = asyncio.run(TTSService().generate_audio(text="hello world", language="en"))
    assert result["audio_data"] == b"ABCD"
    assert result["content_type"] == "audio/mpeg"


def test_voice_mapping_covers_all_default_languages():
    from app.services.enrichment.lang_config import DEFAULT_LANGUAGES
    from app.services.tts_service import VOICE_MAPPING

    for lang in DEFAULT_LANGUAGES:
        assert lang in VOICE_MAPPING, f"TTS 缺 {lang} 音色"
        assert VOICE_MAPPING[lang].get("default")


def test_speech_kwargs_omits_speed_for_gpt4o_mini_tts():
    """gpt-4o-mini-tts 不认 speed 参数(会400):新模型下省略,tts-1 系保留。"""
    svc = TTSService()
    svc.model = "gpt-4o-mini-tts"
    kw = svc._speech_kwargs("alloy", "hi", 1.5)
    assert "speed" not in kw and kw["model"] == "gpt-4o-mini-tts"

    svc.model = "tts-1"
    kw = svc._speech_kwargs("alloy", "hi", 1.5)
    assert kw["speed"] == 1.5


def test_default_tts_model_is_tts1():
    # 成本核算纠正后回退 tts-1(gpt-4o-mini-tts 对中文反贵;质量升级留给 env 切换)
    assert TTSService().model == "tts-1"
