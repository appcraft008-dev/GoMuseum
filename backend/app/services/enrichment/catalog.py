from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml


@dataclass(frozen=True)
class MuseumConfig:
    slug: str
    name_zh: str
    name_en: str
    city_zh: str
    city_en: str
    country: str
    wikidata_qid: str
    category_filter: str
    fetch_limit: int
    sample_size: int
    sample_qids: list[str] = field(default_factory=list)
    categories: list[str] = field(default_factory=list)
    country_lang: str | None = None
    languages: list[str] = field(default_factory=list)


class MuseumCatalog:
    def __init__(self, configs: dict[str, MuseumConfig]):
        self._configs = configs

    @classmethod
    def from_file(cls, path: str | Path) -> "MuseumCatalog":
        data = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
        configs: dict[str, MuseumConfig] = {}
        for slug, m in (data.get("museums") or {}).items():
            configs[slug] = MuseumConfig(
                slug=slug,
                name_zh=m["name_zh"],
                name_en=m["name_en"],
                city_zh=m["city_zh"],
                city_en=m["city_en"],
                country=m["country"],
                wikidata_qid=m["wikidata_qid"],
                category_filter=m["category_filter"],
                fetch_limit=int(m["fetch_limit"]),
                sample_size=int(m["sample_size"]),
                sample_qids=list(m.get("sample_qids") or []),
                categories=list(m.get("categories") or [m["category_filter"]]),
                country_lang=m.get("country_lang"),
                languages=list(m.get("languages") or []),
            )
        return cls(configs)

    def get(self, slug: str) -> MuseumConfig:
        if slug not in self._configs:
            raise KeyError(f"未知馆: {slug}")
        return self._configs[slug]
