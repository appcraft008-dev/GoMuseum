import math
import struct

import pytest

from app.core.exceptions import AIServiceException
from app.services.enrichment.audio_quality import estimate_duration_sec
from app.services.tts_mp3 import Mp3Encoder


def _sine(seconds: float) -> bytes:
    n = int(Mp3Encoder.SAMPLE_RATE * seconds)
    return b"".join(
        struct.pack(
            "<h", int(8000 * math.sin(2 * math.pi * 440 * i / Mp3Encoder.SAMPLE_RATE))
        )
        for i in range(n)
    )


def _encode(chunks):
    enc = Mp3Encoder()
    out = b"".join(enc.encode(c) for c in chunks)
    return out + enc.flush()


def test_160k_duration_estimate_matches():
    mp3 = _encode([_sine(3.0)])
    assert abs(estimate_duration_sec(mp3) - 3.0) / 3.0 < 0.02


def test_odd_byte_chunks_ok_and_same_length():
    pcm = _sine(2.0)
    whole = _encode([pcm])
    odd = _encode([pcm[i : i + 1001] for i in range(0, len(pcm), 1001)])
    assert abs(len(odd) - len(whole)) / len(whole) < 0.02


def test_flush_without_audio_raises():
    with pytest.raises(AIServiceException):
        Mp3Encoder().flush()
