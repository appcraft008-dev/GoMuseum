from __future__ import annotations

import json
from datetime import datetime, timezone


class PackStore:
    """版本化 pack 存取，复用 ObjectStorage（R2/local）。"""

    def __init__(self, storage):
        self._storage = storage

    def _key(self, slug: str) -> str:
        ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%SZ")
        return f"museum-packs/{slug}/{ts}.json"

    def put(self, slug: str, pack: dict) -> str:
        key = self._key(slug)
        self._storage.put(
            key,
            json.dumps(pack, ensure_ascii=False).encode("utf-8"),
            "application/json",
        )
        return key

    def get(self, key: str) -> dict:
        data = self._storage.get(key)
        if data is None:
            raise FileNotFoundError(key)
        return json.loads(data)

    def latest_key(self, slug: str, listing: list[str]) -> str | None:
        ks = [k for k in listing if k.startswith(f"museum-packs/{slug}/")]
        return max(ks) if ks else None
