"""目录层抽象：CatalogSource 列对象产 StubRecord（元数据+身份），供身份去重 + 落 stub。
spec 2026-06-22-universal-catalog-spine-design §4。"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Iterable


@dataclass
class StubRecord:
    inventory_number: str | None
    qid: str | None
    title: str | None
    artist: str | None
    year: str | None
    category: str | None
    image_url: str | None
    popularity: int | None
    owning_museum: str
    source: str
    raw: dict = field(default_factory=dict)


class CatalogSource(ABC):
    name: str = "catalog"

    @abstractmethod
    def list(self, museum_cfg) -> Iterable[StubRecord]:
        """列该馆全部对象，产 StubRecord。"""
        raise NotImplementedError
