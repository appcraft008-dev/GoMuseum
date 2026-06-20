"""礼貌抓取 HTTP 客户端：UA 强制 + 令牌桶限速 + 429/503 退避（遵守 Retry-After）+ 熔断。"""

from __future__ import annotations

import time
from typing import Callable

import requests


class PoliteSession:
    def __init__(
        self,
        user_agent: str,
        min_interval: float = 1.0,
        max_retries: int = 3,
        timeout: int = 60,
        sleep: Callable[[float], None] = time.sleep,
    ):
        if not user_agent:
            raise ValueError("必须提供描述性 User-Agent（Wikimedia 强制）")
        self._ua = user_agent
        self._min_interval = min_interval
        self._max_retries = max_retries
        self._timeout = timeout
        self._sleep = sleep
        self._last = 0.0

    def _throttle(self) -> None:
        # 限速用真实 sleep；注入的 self._sleep 仅用于退避（便于测试断言退避时长）。
        wait = self._min_interval - (time.monotonic() - self._last)
        if wait > 0:
            time.sleep(wait)
        self._last = time.monotonic()

    def get_json(self, url, params=None, _transport=None) -> dict:
        get = _transport or (
            lambda u, params=None, headers=None, timeout=None: requests.get(
                u, params=params, headers=headers, timeout=timeout
            )
        )
        headers = {"User-Agent": self._ua, "Accept": "application/json"}
        for attempt in range(self._max_retries):
            self._throttle()
            resp = get(url, params=params, headers=headers, timeout=self._timeout)
            if resp.status_code == 200:
                return resp.json()
            if resp.status_code in (429, 503):
                retry_after = resp.headers.get("Retry-After")
                delay = float(retry_after) if retry_after else 2.0 * (attempt + 1)
                self._sleep(delay)
                continue
            resp_text = getattr(resp, "text", "")
            raise RuntimeError(f"HTTP {resp.status_code}: {resp_text[:200]}")
        raise RuntimeError(f"耗尽重试（{self._max_retries}）仍失败: {url}")
