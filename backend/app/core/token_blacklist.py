"""Refresh token 撤销名单

刷新令牌轮换：每次使用 refresh token 换新后，旧 token 的 jti 进入撤销名单
（TTL 为其剩余有效期），再次使用即拒绝。优先用 Redis 存储；Redis 不可用时
退化为进程内字典（单实例开发环境可接受）。
"""

import logging
import time
from typing import Optional

import redis

from app.core.config import settings

logger = logging.getLogger(__name__)

_PREFIX = "revoked_jti:"


class TokenBlacklist:
    def __init__(self) -> None:
        self._redis: Optional[redis.Redis] = None
        self._memory: dict[str, float] = {}
        try:
            client = redis.Redis(
                host=getattr(settings, "REDIS_HOST", "localhost"),
                port=int(getattr(settings, "REDIS_PORT", 6379)),
                db=int(getattr(settings, "REDIS_DB", 0)),
                socket_connect_timeout=2,
                decode_responses=True,
            )
            client.ping()
            self._redis = client
        except Exception as e:  # noqa: BLE001
            logger.warning(f"Token blacklist falling back to in-memory store: {e}")

    def revoke(self, jti: str, ttl_seconds: int) -> None:
        if ttl_seconds <= 0:
            return
        if self._redis is not None:
            try:
                self._redis.setex(_PREFIX + jti, ttl_seconds, "1")
                return
            except Exception as e:  # noqa: BLE001
                logger.warning(f"Redis revoke failed, using memory: {e}")
        self._memory[jti] = time.time() + ttl_seconds

    def is_revoked(self, jti: str) -> bool:
        if self._redis is not None:
            try:
                return self._redis.exists(_PREFIX + jti) > 0
            except Exception as e:  # noqa: BLE001
                logger.warning(f"Redis check failed, using memory: {e}")
        expires = self._memory.get(jti)
        if expires is None:
            return False
        if expires < time.time():
            self._memory.pop(jti, None)
            return False
        return True


token_blacklist = TokenBlacklist()
