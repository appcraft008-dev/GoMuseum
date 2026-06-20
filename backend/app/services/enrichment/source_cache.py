"""源抓取结果缓存：抓一次复用（键 source+key+day），走 ObjectStorage（本地/R2）。
重跑/生成/翻译/再生成都不再打源 → 既礼貌又省。"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Callable


class SourceCache:
    def __init__(self, storage, day: str | None = None):
        self._storage = storage
        self._day = day or datetime.now(timezone.utc).strftime("%Y-%m-%d")

    def _key(self, source: str, ident: str) -> str:
        return f"source-cache/{source}/{self._day}/{ident}.json"

    def get_or_fetch(self, source: str, ident: str, fetch: Callable[[], dict]) -> dict:
        key = self._key(source, ident)
        cached = self._storage.get(key)
        if cached is not None:
            return json.loads(cached if isinstance(cached, str) else cached.decode())
        data = fetch()
        self._storage.put(
            key, json.dumps(data, ensure_ascii=False).encode(), "application/json"
        )
        return data
