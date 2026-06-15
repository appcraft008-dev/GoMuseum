"""内容缓存与 AI 用量熔断

- 讲解：按 (artwork, artist, language) 缓存到 Redis，同一展品同语言只生成一次
- TTS：按 (text, language, voice, speed) 哈希缓存 MP3 到磁盘
- 用量熔断：OpenAI 调用按日计数，超过日上限返回 429，防止 API 费用失控

Redis 不可用时讲解缓存退化为直接生成（不阻塞业务），计数退化为进程内字典。
"""

import hashlib
import json
import logging
import time
from datetime import date
from pathlib import Path
from typing import Optional

import redis
from fastapi import HTTPException

from app.core.config import settings

logger = logging.getLogger(__name__)

_EXPLANATION_PREFIX = "explanation:"
_USAGE_PREFIX = "openai_calls:"


def _redis_client() -> Optional[redis.Redis]:
    try:
        client = redis.Redis(
            host=getattr(settings, "REDIS_HOST", "localhost"),
            port=int(getattr(settings, "REDIS_PORT", 6379)),
            db=int(getattr(settings, "REDIS_DB", 0)),
            socket_connect_timeout=2,
            decode_responses=True,
        )
        client.ping()
        return client
    except Exception as e:  # noqa: BLE001
        logger.warning(f"Content cache: redis unavailable, degraded mode: {e}")
        return None


class ContentCache:
    def __init__(self) -> None:
        self._redis = _redis_client()
        self._memory_usage: dict[str, int] = {}
        self.tts_dir = Path(getattr(settings, "TTS_CACHE_DIR", "./tts_cache"))
        self.tts_dir.mkdir(parents=True, exist_ok=True)
        self.explanation_ttl = (
            int(getattr(settings, "EXPLANATION_CACHE_TTL_DAYS", 30)) * 86400
        )
        self.daily_limit = int(getattr(settings, "OPENAI_DAILY_CALL_LIMIT", 2000))

    # ── 讲解缓存 ──────────────────────────────────────────────
    @staticmethod
    def _explanation_key(artwork: str, artist: str, language: str) -> str:
        raw = f"{artwork.strip().lower()}|{artist.strip().lower()}|{language.lower()}"
        return _EXPLANATION_PREFIX + hashlib.sha256(raw.encode()).hexdigest()

    def get_explanation(
        self, artwork: str, artist: str, language: str
    ) -> Optional[dict]:
        if self._redis is None:
            return None
        try:
            cached = self._redis.get(self._explanation_key(artwork, artist, language))
            return json.loads(cached) if cached else None
        except Exception as e:  # noqa: BLE001
            logger.warning(f"Explanation cache read failed: {e}")
            return None

    def set_explanation(
        self, artwork: str, artist: str, language: str, payload: dict
    ) -> None:
        if self._redis is None:
            return
        try:
            self._redis.setex(
                self._explanation_key(artwork, artist, language),
                self.explanation_ttl,
                json.dumps(payload, ensure_ascii=False),
            )
        except Exception as e:  # noqa: BLE001
            logger.warning(f"Explanation cache write failed: {e}")

    # ── TTS 磁盘缓存 ──────────────────────────────────────────
    def _tts_path(self, text: str, language: str, voice: str, speed: float) -> Path:
        raw = f"{text}|{language}|{voice}|{speed}"
        return self.tts_dir / (hashlib.sha256(raw.encode()).hexdigest() + ".mp3")

    def get_tts(
        self, text: str, language: str, voice: str, speed: float
    ) -> Optional[bytes]:
        path = self._tts_path(text, language, voice, speed)
        if path.exists():
            try:
                return path.read_bytes()
            except OSError as e:
                logger.warning(f"TTS cache read failed: {e}")
        return None

    def set_tts(
        self, text: str, language: str, voice: str, speed: float, audio: bytes
    ) -> None:
        path = self._tts_path(text, language, voice, speed)
        try:
            tmp = path.with_suffix(".tmp")
            tmp.write_bytes(audio)
            tmp.replace(path)
        except OSError as e:
            logger.warning(f"TTS cache write failed: {e}")

    # ── 用量熔断 ──────────────────────────────────────────────
    def check_openai_budget(self) -> None:
        """计入一次 OpenAI 调用；超过日上限抛 429"""
        key = _USAGE_PREFIX + date.today().isoformat()
        count: int
        if self._redis is not None:
            try:
                count = self._redis.incr(key)
                if count == 1:
                    self._redis.expire(key, 86400 * 2)
            except Exception as e:  # noqa: BLE001
                logger.warning(f"Usage counter redis failed: {e}")
                count = self._memory_incr(key)
        else:
            count = self._memory_incr(key)

        if count > self.daily_limit:
            logger.error(f"OpenAI daily call limit reached: {count}/{self.daily_limit}")
            raise HTTPException(
                status_code=429,
                detail={
                    "error": "DailyBudgetExceeded",
                    "detail": "AI service daily budget exhausted, try again tomorrow",
                },
            )
        if count == int(self.daily_limit * 0.8):
            logger.warning(
                f"OpenAI usage at 80% of daily limit ({count}/{self.daily_limit})"
            )

    def _memory_incr(self, key: str) -> int:
        self._memory_usage[key] = self._memory_usage.get(key, 0) + 1
        return self._memory_usage[key]


_content_cache: Optional[ContentCache] = None


def get_content_cache() -> ContentCache:
    global _content_cache
    if _content_cache is None:
        _content_cache = ContentCache()
    return _content_cache
