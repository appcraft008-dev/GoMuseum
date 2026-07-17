"""锁死 TTS 真流式:generate_audio_stream 必须走 with_streaming_response(边收边吐),
禁止缓冲式 create()(await 时整段下载完,客户端干等 ~20s 后一次性收到——真机实测教训)。"""

import pytest

import app.services.tts_service as tts_mod
from app.services.tts_service import TTSService


class _FakeStreamedResponse:
    async def iter_bytes(self, chunk_size=4096):
        for chunk in (b"aa", b"bb", b"cc"):
            yield chunk


class _FakeStreamCM:
    async def __aenter__(self):
        return _FakeStreamedResponse()

    async def __aexit__(self, *a):
        return False


class _FakeSpeech:
    def __init__(self):
        outer = self

        class _WSR:
            def create(self, **kw):
                outer.stream_called = True
                return _FakeStreamCM()

        self.with_streaming_response = _WSR()
        self.stream_called = False

    async def create(self, **kw):  # 缓冲式老路——谁调谁错
        raise AssertionError("buffered speech.create() called; must use streaming")


class _FakeClient:
    def __init__(self):
        class _Audio:
            pass

        self.audio = _Audio()
        self.audio.speech = _FakeSpeech()


@pytest.mark.asyncio
async def test_generate_audio_stream_uses_streaming_response(monkeypatch):
    fake = _FakeClient()
    monkeypatch.setattr(tts_mod, "_get_openai_client", lambda: fake)
    got = []
    async for chunk in TTSService().generate_audio_stream("hello", "en"):
        got.append(chunk)
    assert got == [b"aa", b"bb", b"cc"]
    assert fake.audio.speech.stream_called
