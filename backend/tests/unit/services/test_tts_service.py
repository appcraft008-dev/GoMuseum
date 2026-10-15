"""Google Chirp 3 HD 流式 TTS(spec 2026-10-15)。gRPC 全部打桩,不连 Google。"""

import asyncio
import math
import struct
import threading

import pytest

import app.services.tts_service as tts_mod
from app.core.exceptions import AIServiceException
from app.services.tts_mp3 import Mp3Encoder
from app.services.tts_service import ENGINE, VOICES, TTSService, voice_name


def _pcm(seconds: float) -> bytes:
    n = int(Mp3Encoder.SAMPLE_RATE * seconds)
    return b"".join(
        struct.pack("<h", int(8000 * math.sin(2 * math.pi * 440 * i / 24000)))
        for i in range(n)
    )


class _Resp:
    def __init__(self, b):
        self.audio_content = b


class _FakeClient:
    """记下发送序列;按 plan 吐 PCM。plan 里放 Exception 表示在那一步抛。"""

    def __init__(self, plans):
        self.plans = list(plans)  # 每次调用一个 plan
        self.sent = []
        self.calls = 0

    def streaming_synthesize(self, requests, timeout=None):
        self.calls += 1
        self.timeout = timeout
        self.sent.append(list(requests))
        plan = self.plans.pop(0)

        def gen():
            for item in plan:
                if isinstance(item, Exception):
                    raise item
                yield _Resp(item)

        return gen()


def _patch(monkeypatch, *plans):
    fake = _FakeClient(plans)
    monkeypatch.setattr(tts_mod, "_get_client", lambda: fake)
    monkeypatch.setattr(tts_mod, "record_llm_usage", lambda *a, **k: None)
    return fake


TEXT_EN = "This painting is large. It hangs in the Louvre today."  # ~3s 合理时长


def test_voices_cover_default_languages():
    from app.services.enrichment.lang_config import DEFAULT_LANGUAGES

    for lang in DEFAULT_LANGUAGES:
        locale, voice, rate = VOICES[lang]
        assert voice and 0.8 <= rate <= 1.1
    assert VOICES["zh-hant"][0] == "cmn-CN"
    assert voice_name("zh") == "cmn-CN-Chirp3-HD-Laomedeia"
    assert voice_name("zh-hant") == "cmn-CN-Chirp3-HD-Despina"


def test_sends_config_then_one_input_per_sentence(monkeypatch):
    fake = _patch(monkeypatch, [_pcm(3.5)])
    asyncio.run(TTSService().generate_audio(TEXT_EN, "en"))
    reqs = fake.sent[0]
    cfg = reqs[0].streaming_config
    assert cfg.voice.name == "en-US-Chirp3-HD-Autonoe"
    assert abs(cfg.streaming_audio_config.speaking_rate - 1.05) < 1e-6
    assert [r.input.text for r in reqs[1:]] == [
        "This painting is large.",
        "It hangs in the Louvre today.",
    ]
    assert fake.timeout == 60


def test_generate_audio_returns_160k_mp3(monkeypatch):
    _patch(monkeypatch, [_pcm(1.5), _pcm(2.0)])
    r = asyncio.run(TTSService().generate_audio(TEXT_EN, "en"))
    assert r["content_type"] == "audio/mpeg"
    assert r["voice"] == "en-US-Chirp3-HD-Autonoe"
    assert abs(r["duration_estimate"] - 3.5) < 0.1


def test_two_asyncio_run_calls_on_same_service(monkeypatch):
    # lazy_audio._synth 每次 asyncio.run 新建 loop —— 不能复用绑定旧 loop 的东西
    _patch(monkeypatch, [_pcm(3.5)], [_pcm(3.5)])
    svc = TTSService()
    asyncio.run(svc.generate_audio(TEXT_EN, "en"))
    asyncio.run(svc.generate_audio(TEXT_EN, "en"))


def test_retry_once_when_failing_before_first_chunk(monkeypatch):
    fake = _patch(monkeypatch, [RuntimeError("unavailable")], [_pcm(3.5)])
    asyncio.run(TTSService().generate_audio(TEXT_EN, "en"))
    assert fake.calls == 2


def test_no_retry_after_first_chunk(monkeypatch):
    fake = _patch(monkeypatch, [_pcm(1.0), RuntimeError("reset")], [_pcm(3.5)])
    with pytest.raises(AIServiceException):
        asyncio.run(TTSService().generate_audio(TEXT_EN, "en"))
    assert fake.calls == 1


def test_short_audio_fails_self_check(monkeypatch):
    _patch(monkeypatch, [_pcm(1.0)])
    with pytest.raises(AIServiceException):
        asyncio.run(TTSService().generate_audio("长句。" * 300, "zh"))


def test_empty_text_raises(monkeypatch):
    fake = _patch(monkeypatch)
    with pytest.raises(AIServiceException):
        asyncio.run(TTSService().generate_audio("  \n ", "en"))
    assert fake.calls == 0


def test_unknown_language_falls_back_to_en(monkeypatch):
    fake = _patch(monkeypatch, [_pcm(3.5)])
    r = asyncio.run(TTSService().generate_audio(TEXT_EN, "pt"))
    assert r["language"] == "en"
    assert fake.sent[0][0].streaming_config.voice.name == "en-US-Chirp3-HD-Autonoe"


@pytest.mark.asyncio
async def test_stream_yields_before_google_finishes(monkeypatch):
    """真流式:Google 还没吐完,客户端已经拿到第一块 MP3。"""
    release = threading.Event()

    class _Blocking(_FakeClient):
        def streaming_synthesize(self, requests, timeout=None):
            list(requests)

            def gen():
                yield _Resp(_pcm(1.0))
                release.wait(5)
                yield _Resp(_pcm(2.5))

            return gen()

    monkeypatch.setattr(tts_mod, "_get_client", lambda: _Blocking([]))
    monkeypatch.setattr(tts_mod, "record_llm_usage", lambda *a, **k: None)
    agen = TTSService().generate_audio_stream(TEXT_EN, "en")
    first = await asyncio.wait_for(agen.__anext__(), timeout=3)
    assert first and not release.is_set()
    release.set()
    rest = [c async for c in agen]
    assert rest


def test_records_usage_with_engine(monkeypatch):
    fake = _FakeClient([[_pcm(3.5)]])
    seen = []
    monkeypatch.setattr(tts_mod, "_get_client", lambda: fake)
    monkeypatch.setattr(tts_mod, "record_llm_usage", lambda *a, **k: seen.append(a))
    asyncio.run(TTSService().generate_audio(TEXT_EN, "en"))
    assert seen == [("tts", ENGINE, len(TEXT_EN), 0)]


def test_supported_voices_shape():
    v = TTSService().get_supported_voices("fr")
    assert v == {
        "language": "fr",
        "default_voice": "fr-FR-Chirp3-HD-Callirrhoe",
        "available_voices": ["fr-FR-Chirp3-HD-Callirrhoe"],
    }
