from __future__ import annotations

import time
from typing import Iterable

import requests

from app.services.enrichment.catalog import MuseumConfig
from app.services.enrichment.sources.base import ObjectContribution, Source

SPARQL_ENDPOINT = "https://query.wikidata.org/sparql"
USER_AGENT = "GoMuseum/0.1 (enrichment; contact: dev@gomuseum.app)"

QUERY = """
SELECT ?item ?label_zh ?label_en ?creator_zh ?creator_en ?year ?image ?links ?inventory WHERE {{
  ?item wdt:P195 wd:{museum} . ?item wdt:P31 wd:{category} . ?item wdt:P18 ?image .
  ?item wikibase:sitelinks ?links .
  OPTIONAL {{ ?item rdfs:label ?label_zh . FILTER(LANG(?label_zh)="zh") }}
  OPTIONAL {{ ?item rdfs:label ?label_en . FILTER(LANG(?label_en)="en") }}
  OPTIONAL {{ ?item wdt:P170 ?creator .
    OPTIONAL {{ ?creator rdfs:label ?creator_zh . FILTER(LANG(?creator_zh)="zh") }}
    OPTIONAL {{ ?creator rdfs:label ?creator_en . FILTER(LANG(?creator_en)="en") }} }}
  OPTIONAL {{ ?item wdt:P571 ?date . BIND(YEAR(?date) AS ?year) }}
  OPTIONAL {{ ?item wdt:P217 ?inventory }}
}} ORDER BY DESC(?links) LIMIT {limit} OFFSET {offset}
"""

_PAGE = 200  # 每页；大馆翻页

# category_filter(Wikidata QID) → canonical 类型名；未知 QID 回退 painting
_CATEGORY_BY_QID = {
    "Q3305213": "painting",
    "Q860861": "sculpture",
    "Q125191": "photograph",
}


class WikidataSource(Source):
    name = "wikidata"

    def _run_query(self, sparql: str) -> list[dict]:
        r = requests.get(
            SPARQL_ENDPOINT,
            params={"query": sparql, "format": "json"},
            headers={
                "User-Agent": USER_AGENT,
                "Accept": "application/sparql-results+json",
            },
            timeout=60,
        )
        r.raise_for_status()
        return r.json()["results"]["bindings"]

    def fetch(self, cfg: MuseumConfig) -> Iterable[ObjectContribution]:
        category = _CATEGORY_BY_QID.get(cfg.category_filter, "painting")
        seen: set[str] = set()
        fetched = 0
        offset = 0
        while fetched < cfg.fetch_limit:
            page = min(_PAGE, cfg.fetch_limit - fetched)
            rows = self._run_query(
                QUERY.format(
                    museum=cfg.wikidata_qid,
                    category=cfg.category_filter,
                    limit=page,
                    offset=offset,
                )
            )
            if not rows:
                break
            for row in rows:
                qid = row["item"]["value"].rsplit("/", 1)[-1]
                if qid in seen:
                    continue
                seen.add(qid)
                yield ObjectContribution(
                    source="wikidata",
                    qid=qid,
                    raw=row,
                    fields={
                        "category": category,
                        "title_zh": _v(row, "label_zh"),
                        "title_en": _v(row, "label_en"),
                        "artist_zh": _v(row, "creator_zh"),
                        "artist_en": _v(row, "creator_en"),
                        "year": _v(row, "year"),
                        "inventory_number": _v(row, "inventory"),
                        "popularity": int(_v(row, "links") or 0),
                        "image_url": _v(row, "image"),
                    },
                )
            fetched += len(rows)
            offset += len(rows)
            time.sleep(1)  # 礼貌限速


def _v(row: dict, key: str):
    cell = row.get(key)
    return cell["value"] if cell else None
