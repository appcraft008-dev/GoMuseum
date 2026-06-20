from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Iterable

from app.services.enrichment.catalog import MuseumConfig


@dataclass
class ObjectContribution:
    source: str
    qid: str
    fields: dict = field(default_factory=dict)  # canonical 候选字段
    raw: dict = field(default_factory=dict)  # 该源原始包


class Source(ABC):
    name: str

    @abstractmethod
    def fetch(self, cfg: MuseumConfig) -> Iterable[ObjectContribution]:
        """抓某馆 → 逐 object 产出贡献。"""

    def probe(self, external_ids: dict) -> bool:
        """该源是否适用于带这些 Wikidata 外部 ID 的对象。
        默认 True(如 Wikidata/Wikipedia 普适);按外部 ID 路由的源(如 Joconde)重写。"""
        return True
