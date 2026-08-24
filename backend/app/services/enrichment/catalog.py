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
    # 每馆补充源(Wikidata 是脊柱不在此列);缺省只有全球通用的 wikipedia
    sources: list[str] = field(default_factory=lambda: ["wikipedia"])
    # Joconde 官方馆名(data.culture.gouv.fr 的 nom_officiel_musee),配了才跑 JocondeCatalog
    joconde_museum: str | None = None
    # 多QID收藏锚点(卢浮宫等部门制馆:P195 挂部门而非馆本体;spec 2026-07-21)。
    # 缺省空 → 消费方回退 [wikidata_qid],存量单锚点馆零影响。
    collection_qids: list[str] = field(default_factory=list)
    # 百科全书式大馆:整部门全收,catalog SPARQL 去掉 category 过滤(古物/装饰艺术
    # P31 长尾几百种无法逐个列 categories)。缺省 False → 存量馆保持类目过滤不变。
    collect_all_types: bool = False
    # 馆介绍的接地材料来源 QID。缺省 None → 用 wikidata_qid。
    # 用于「馆本体没有 enwiki 条目、英文文章挂在建筑上」的馆(小皇宫:馆=Q59546080
    # 只有 commonswiki,Petit Palais 建筑=Q820892 才有 enwiki)。显式配置而非自动
    # 跟随 P276——P276 也可能指向城市,那会拿城市文章当馆介绍材料。
    intro_qid: str | None = None


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
                sources=list(m.get("sources") or ["wikipedia"]),
                joconde_museum=m.get("joconde_museum"),
                collection_qids=list(m.get("collection_qids") or []),
                collect_all_types=bool(m.get("collect_all_types") or False),
                intro_qid=m.get("intro_qid"),
            )
        return cls(configs)

    def get(self, slug: str) -> MuseumConfig:
        if slug not in self._configs:
            raise KeyError(f"未知馆: {slug}")
        return self._configs[slug]
