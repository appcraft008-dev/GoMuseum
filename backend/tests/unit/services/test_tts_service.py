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
    assert fake.timeout == 45  # 两次尝试合计 < 段级锁 2 分钟


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
    from google.api_core import exceptions as gexc

    fake = _patch(monkeypatch, [gexc.ServiceUnavailable("unavailable")], [_pcm(3.5)])
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


def test_current_engine_marker_is_google():
    from app.services.content_repo import _current_tts_engine

    assert _current_tts_engine() == ENGINE == "google-chirp3-hd"


def test_cost_report_has_google_price():
    import importlib.util
    import pathlib

    p = pathlib.Path(__file__).resolve().parents[3] / "scripts" / "llm_cost_report.py"
    spec = importlib.util.spec_from_file_location("llm_cost_report", p)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    assert mod.PRICES["google-chirp3-hd"] == (30.0, 0.0)


def test_tts_generate_request_caps_text_length():
    # 换 Google 后切句可吃任意长文本,tts-1 原有的 4096 字隐性闸没了 → 显式上限(prod 正文最长 2049)
    import pydantic

    from app.api.v1.endpoints.content import TTSRequest

    TTSRequest(text="x" * 5000)
    with pytest.raises(pydantic.ValidationError):
        TTSRequest(text="x" * 5001)


def test_no_retry_on_non_transient_error(monkeypatch):
    # key 配错这类错误重试也没用,只会多等一倍
    from google.api_core import exceptions as gexc

    fake = _patch(monkeypatch, [gexc.PermissionDenied("bad key")], [_pcm(3.5)])
    with pytest.raises(AIServiceException):
        asyncio.run(TTSService().generate_audio(TEXT_EN, "en"))
    assert fake.calls == 1


def test_usage_recorded_per_attempt(monkeypatch):
    # Google 按每次请求的字符计费:重试那次也要记
    from google.api_core import exceptions as gexc

    fake = _FakeClient([[gexc.ServiceUnavailable("x")], [_pcm(3.5)]])
    seen = []
    monkeypatch.setattr(tts_mod, "_get_client", lambda: fake)
    monkeypatch.setattr(tts_mod, "record_llm_usage", lambda *a, **k: seen.append(a))
    asyncio.run(TTSService().generate_audio(TEXT_EN, "en"))
    assert seen == [("tts", ENGINE, len(TEXT_EN), 0)] * 2


def test_short_text_skips_ratio_self_check(monkeypatch):
    # "Hi." 期望 0.2s,Chirp 带首尾静音必超 2.2 倍 —— 极短文本不做时长比例自检
    _patch(monkeypatch, [_pcm(2.0)])
    r = asyncio.run(TTSService().generate_audio("Hi.", "en"))
    assert r["size_bytes"] > 0


def test_runs_on_dedicated_tts_threads(monkeypatch):
    # 不占默认线程池(那里还有 _prepare_sync/_persist_sync 等 to_thread)
    names = []

    class _Named(_FakeClient):
        def streaming_synthesize(self, requests, timeout=None):
            names.append(threading.current_thread().name)
            return super().streaming_synthesize(requests, timeout)

    monkeypatch.setattr(tts_mod, "_get_client", lambda: _Named([[_pcm(3.5)]]))
    monkeypatch.setattr(tts_mod, "record_llm_usage", lambda *a, **k: None)
    asyncio.run(TTSService().generate_audio(TEXT_EN, "en"))
    assert names and names[0].startswith("tts")


def test_client_created_once_under_concurrency(monkeypatch):
    import time as _t

    from google.cloud import texttospeech

    made = []

    def slow_client(**kw):
        _t.sleep(0.05)
        made.append(1)
        return object()

    monkeypatch.setattr(tts_mod, "_client", None)
    monkeypatch.setattr(tts_mod.settings, "GOOGLE_TTS_API_KEY", "k")
    monkeypatch.setattr(texttospeech, "TextToSpeechClient", slow_client)
    ts = [threading.Thread(target=tts_mod._get_client) for _ in range(4)]
    [t.start() for t in ts]
    [t.join() for t in ts]
    assert len(made) == 1


def test_drain_returns_quietly_when_loop_closed():
    # asyncio.run 收尾后 worker 还在跑:往已关闭的 loop 投递不应抛到 executor future 里
    loop = asyncio.new_event_loop()
    loop.close()
    tts_mod._drain(loop, asyncio.Queue(), lambda: iter([b"a", b"b"]), object())


def test_zh_slower_with_long_pause_between_paragraphs(monkeypatch):
    """10-17 用户耳选 C 版:zh 语速 0.92、段间 [pause long];仍按句送(整段送会吞句)。"""
    fake = _patch(monkeypatch, [_pcm(6.0)])
    text = "蒙娜丽莎是一幅肖像。她在微笑。\n\n画家是达·芬奇。"
    asyncio.run(TTSService().generate_audio(text, "zh"))
    reqs = fake.sent[0]
    assert (
        abs(reqs[0].streaming_config.streaming_audio_config.speaking_rate - 0.92) < 1e-6
    )
    assert [r.input.markup for r in reqs[1:]] == [
        "蒙娜丽莎是一幅肖像。",
        "她在微笑。",
        "[pause long] 画家是达·芬奇。",
    ]
