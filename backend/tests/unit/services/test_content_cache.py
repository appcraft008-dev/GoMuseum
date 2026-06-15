"""Unit tests for ContentCache: TTS 磁盘缓存、讲解缓存键、日预算熔断"""

import pytest
from fastapi import HTTPException

from app.services.content_cache import ContentCache


@pytest.fixture()
def cache(tmp_path, monkeypatch):
    # 隔离磁盘目录；强制 Redis 不可用走内存路径
    monkeypatch.setattr("app.services.content_cache._redis_client", lambda: None)
    monkeypatch.setattr(
        "app.services.content_cache.settings.TTS_CACHE_DIR",
        str(tmp_path / "tts"),
        raising=False,
    )
    return ContentCache()


def test_tts_disk_cache_roundtrip(cache):
    assert cache.get_tts("你好", "zh", "default", 1.0) is None
    cache.set_tts("你好", "zh", "default", 1.0, b"MP3DATA")
    assert cache.get_tts("你好", "zh", "default", 1.0) == b"MP3DATA"
    # 不同参数不同键
    assert cache.get_tts("你好", "zh", "default", 1.5) is None
    assert cache.get_tts("你好", "en", "default", 1.0) is None


def test_explanation_cache_degrades_without_redis(cache):
    # Redis 不可用时读写都安全地退化为 no-op
    assert cache.get_explanation("卧室", "梵高", "zh") is None
    cache.set_explanation("卧室", "梵高", "zh", {"title": "卧室"})
    assert cache.get_explanation("卧室", "梵高", "zh") is None


def test_budget_guard_raises_429_when_exhausted(cache):
    cache.daily_limit = 3
    for _ in range(3):
        cache.check_openai_budget()
    with pytest.raises(HTTPException) as exc:
        cache.check_openai_budget()
    assert exc.value.status_code == 429
