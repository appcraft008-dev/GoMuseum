"""本地文件实现：落盘到 root_dir/key，public_url 走后端静态前缀。"""

from pathlib import Path
from typing import Optional

from app.services.storage.base import ObjectStorage


class LocalObjectStorage(ObjectStorage):
    def __init__(self, root_dir: str, public_base_url: str):
        self._root = Path(root_dir)
        self._base = public_base_url.rstrip("/")

    def _path(self, key: str) -> Path:
        return self._root / key

    def put(self, key: str, data: bytes, content_type: str) -> None:
        p = self._path(key)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data)

    def get(self, key: str) -> Optional[bytes]:
        p = self._path(key)
        return p.read_bytes() if p.exists() else None

    def exists(self, key: str) -> bool:
        return self._path(key).exists()

    def delete(self, key: str) -> None:
        p = self._path(key)
        if p.exists():
            p.unlink()

    def public_url(self, key: str) -> str:
        return f"{self._base}/{key}"
