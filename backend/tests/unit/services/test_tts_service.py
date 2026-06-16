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
