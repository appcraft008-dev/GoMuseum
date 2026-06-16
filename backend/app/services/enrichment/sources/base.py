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
