"""TTS:Google Chirp 3 HD 流式合成(替换 tts-1,spec 2026-10-15)。

只用于懒生成兜底与 /tts/generate;批量音频是 VoxCPM2(离线)。
- 发送:同步 gRPC streaming_synthesize,首个 request 是配置,之后**一句一个 input**
  (REST 整段送中文会随机 400;流式会静默吞超长句句尾 → 切句见 tts_text)。
- 同步客户端 + 线程桥接,不用 grpc.aio:lazy_audio._synth 每次 asyncio.run 新建 loop,
  aio channel 绑定旧 loop 会炸。
- 输出 160 kbps MP3(质量闸按 160k 估时长),结尾跑 check_audio,不过就抛错 → 不落库。
"""

import asyncio
import hashlib
import logging
from typing import AsyncIterator, Callable, Dict, Iterator, Optional

from app.core.config import settings
from app.core.exceptions import AIServiceException
from app.services.enrichment.audio_quality import check_audio, estimate_duration_sec
from app.services.llm_usage import record_llm_usage
from app.services.tts_mp3 import Mp3Encoder
from app.services.tts_text import split_sentences

logger = logging.getLogger(__name__)

ENGINE = "google-chirp3-hd"
_DEADLINE_S = 60

# 语言 → (locale, Chirp 3 HD 声音, speaking_rate)。用户 10-15 逐语言耳选,语速对齐 VoxCPM2 成品。
# zh-hant 用 cmn-CN:Chirp 3 HD 没有 cmn-TW(tts-1 / VoxCPM2 也是普通话读繁体)。
VOICES: Dict[str, tuple] = {
    "zh": ("cmn-CN", "Laomedeia", 1.03),
    "zh-hant": ("cmn-CN", "Despina", 1.02),
    "en": ("en-US", "Autonoe", 1.05),
    "fr": ("fr-FR", "Callirrhoe", 0.90),
    "de": ("de-DE", "Achernar", 0.93),
    "es": ("es-ES", "Aoede", 0.98),
    "it": ("it-IT", "Autonoe", 1.02),
    "pl": ("pl-PL", "Kore", 0.97),
    "ja": ("ja-JP", "Aoede", 0.99),
    "ko": ("ko-KR", "Erinome", 0.98),
}

_client = None


def _get_client():
    """按进程懒建(测试打桩此处)。"""
    global _client
    if _client is None:
        if not settings.GOOGLE_TTS_API_KEY:
            raise AIServiceException("GOOGLE_TTS_API_KEY 未配置")
        from google.cloud import texttospeech

        _client = texttospeech.TextToSpeechClient(
            client_options={"api_key": settings.GOOGLE_TTS_API_KEY}
        )
    return _client


def _lang(language: str) -> str:
    return language if language in VOICES else "en"


def voice_name(language: str) -> str:
    locale, voice, _ = VOICES[_lang(language)]
    return f"{locale}-Chirp3-HD-{voice}"


def _requests(sentences, language: str):
    from google.cloud import texttospeech as tts

    locale, _, rate = VOICES[language]
    yield tts.StreamingSynthesizeRequest(
        streaming_config=tts.StreamingSynthesizeConfig(
            voice=tts.VoiceSelectionParams(
                language_code=locale, name=voice_name(language)
            ),
            streaming_audio_config=tts.StreamingAudioConfig(
                audio_encoding=tts.AudioEncoding.PCM,
                sample_rate_hertz=Mp3Encoder.SAMPLE_RATE,
                speaking_rate=rate,
            ),
        )
    )
    for s in sentences:
        yield tts.StreamingSynthesizeRequest(input=tts.StreamingSynthesisInput(text=s))


def _pcm_chunks(sentences, language: str) -> Iterator[bytes]:
    """同步迭代 PCM。首块到达前失败重试 1 次;吐过音频后失败不重试。"""
    for attempt in (1, 2):
        got = False
        try:
            stream = _get_client().streaming_synthesize(
                _requests(sentences, language), timeout=_DEADLINE_S
            )
            for resp in stream:
                if resp.audio_content:
                    got = True
                    yield resp.audio_content
            return
        except AIServiceException:
            raise
        except Exception as e:
            if got or attempt == 2:
                raise AIServiceException(f"Google TTS 失败: {e}") from e
            logger.warning(f"Google TTS 首块前失败,重试一次: {e}")


async def _iterate_in_thread(
    make_iter: Callable[[], Iterator[bytes]],
) -> AsyncIterator[bytes]:
    """在线程里跑同步迭代器,经队列交回事件循环,边收边吐。"""
    loop = asyncio.get_running_loop()
    queue: asyncio.Queue = asyncio.Queue()
    done = object()

    def worker():
        try:
            for item in make_iter():
                loop.call_soon_threadsafe(queue.put_nowait, item)
            loop.call_soon_threadsafe(queue.put_nowait, done)
        except BaseException as e:  # 交给消费方抛
            loop.call_soon_threadsafe(queue.put_nowait, e)

    fut = loop.run_in_executor(None, worker)
    while True:
        item = await queue.get()
        if item is done:
            break
        if isinstance(item, BaseException):
            raise item
        yield item
    await fut


class TTSService:
    """Google Chirp 3 HD。`voice` / `speed` 参数保留以兼容调用方与 /tts/generate,但忽略
    (声音按语言固定;倍速在 App 播放端做)。"""

    async def generate_audio_stream(
        self,
        text: str,
        language: str = "en",
        voice: Optional[str] = None,
        speed: float = 1.0,
    ) -> AsyncIterator[bytes]:
        language = _lang(language)
        sentences = split_sentences(text, language)
        if not sentences:
            raise AIServiceException("TTS 正文为空")
        record_llm_usage("tts", ENGINE, len(text), 0)
        enc = Mp3Encoder()
        out = bytearray()
        async for pcm in _iterate_in_thread(lambda: _pcm_chunks(sentences, language)):
            mp3 = enc.encode(pcm)
            if mp3:
                out += mp3
                yield mp3
        tail = enc.flush()
        out += tail
        verdict = check_audio(bytes(out), text=text, language=language)
        if not verdict.ok:
            raise AIServiceException(f"TTS 音频自检不过: {verdict.reason}")
        if tail:
            yield tail

    async def generate_audio(
        self,
        text: str,
        language: str = "en",
        voice: Optional[str] = None,
        speed: float = 1.0,
    ) -> Dict[str, object]:
        language = _lang(language)
        data = b"".join([c async for c in self.generate_audio_stream(text, language)])
        return {
            "audio_data": data,
            "content_type": "audio/mpeg",
            "duration_estimate": estimate_duration_sec(data),
            "voice": voice_name(language),
            "language": language,
            "text_hash": self.generate_text_hash(text, language),
            "size_bytes": len(data),
        }

    def get_supported_voices(self, language: str = "en") -> Dict[str, object]:
        language = _lang(language)
        return {
            "language": language,
            "default_voice": voice_name(language),
            "available_voices": [voice_name(language)],
        }

    def generate_text_hash(
        self,
        text: str,
        language: str = "en",
        voice: Optional[str] = None,
        speed: float = 1.0,
    ) -> str:
        return hashlib.sha256(
            f"{text}:{_lang(language)}:{voice_name(language)}".encode()
        ).hexdigest()[:16]


_tts_service_instance = None


def get_tts_service() -> TTSService:
    global _tts_service_instance
    if _tts_service_instance is None:
        _tts_service_instance = TTSService()
    return _tts_service_instance
