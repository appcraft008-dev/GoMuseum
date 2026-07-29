"""对象存储统一抽象：图片/音频。实现见 local.py（本地）、r2.py（Cloudflare R2）。"""

from abc import ABC, abstractmethod
from typing import Optional


class ObjectStorage(ABC):
    @abstractmethod
    def put(self, key: str, data: bytes, content_type: str) -> None:
        """写入对象。key 形如 'images/Q12418/primary.jpg'。"""

    @abstractmethod
    def get(self, key: str) -> Optional[bytes]:
        """读取对象；不存在返回 None。"""

    @abstractmethod
    def exists(self, key: str) -> bool: ...

    @abstractmethod
    def delete(self, key: str) -> None: ...

    def list_keys(self, prefix: str) -> "Iterator[tuple[str, int, object]]":
        """枚举前缀下的对象:(key, 字节数, 最后修改时间)。孤儿对账需要。"""
        raise NotImplementedError

    @abstractmethod
    def public_url(self, key: str) -> str:
        """返回可直接给客户端展示的 URL。"""
