from __future__ import annotations

import time
from typing import Iterable

import requests

from app.services.enrichment.catalog import MuseumConfig
from app.services.enrichment.category_config import category_for
from app.services.enrichment.sources.base import ObjectContribution, Source

SPARQL_ENDPOINT = "https://query.wikidata.org/sparql"
USER_AGENT = "GoMuseum/0.1 (enrichment; contact: dev@gomuseum.app)"

QUERY = """
SELECT ?item ?label_zh ?label_en ?creator_zh ?creator_en ?year ?image ?links ?inventory ?p31 ?joconde WHERE {{
  VALUES ?cat {{ {cat_values} }}
  ?item wdt:P195 wd:{museum} . ?item wdt:P31 ?cat . ?item wdt:P31 ?p31 .
  ?item wikibase:sitelinks ?links .
  OPTIONAL {{ ?item wdt:P18 ?image }}
  OPTIONAL {{ ?item rdfs:label ?label_zh . FILTER(LANG(?label_zh)="zh") }}
  OPTIONAL {{ ?item rdfs:label ?label_en . FILTER(LANG(?label_en)="en") }}
  OPTIONAL {{ ?item wdt:P170 ?creator .
    OPTIONAL {{ ?creator rdfs:label ?creator_zh . FILTER(LANG(?creator_zh)="zh") }}
    OPTIONAL {{ ?creator rdfs:label ?creator_en . FILTER(LANG(?creator_en)="en") }} }}
  OPTIONAL {{ ?item wdt:P571 ?date . BIND(YEAR(?date) AS ?year) }}
  OPTIONAL {{ ?item wdt:P217 ?inventory }}
  OPTIONAL {{ ?item wdt:P347 ?joconde }}
}} ORDER BY DESC(?links) LIMIT {limit} OFFSET {offset}
"""

_PAGE = 200  # 每页；大馆翻页


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
        cats = cfg.categories or [cfg.category_filter]
        cat_values = " ".join(f"wd:{q}" for q in cats)
        seen: set[str] = set()
        fetched = 0
        offset = 0
        while fetched < cfg.fetch_limit:
            page = min(_PAGE, cfg.fetch_limit - fetched)
            rows = self._run_query(
                QUERY.format(
                    museum=cfg.wikidata_qid,
                    cat_values=cat_values,
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
                p31_qid = (row.get("p31", {}) or {}).get("value", "").rsplit("/", 1)[-1]
                ext = {}
                jo = _v(row, "joconde")
                if jo:
                    ext["P347"] = jo
                yield ObjectContribution(
                    source="wikidata",
                    qid=qid,
                    raw=row,
                    fields={
                        "category": category_for(p31_qid),
                        "title_zh": _v(row, "label_zh"),
                        "title_en": _v(row, "label_en"),
                        "artist_zh": _v(row, "creator_zh"),
                        "artist_en": _v(row, "creator_en"),
                        "year": _v(row, "year"),
                        "inventory_number": _v(row, "inventory"),
                        "popularity": int(_v(row, "links") or 0),
                        "image_url": _v(row, "image"),
                        "external_ids": ext,
                    },
                )
            fetched += len(rows)
            offset += len(rows)
            time.sleep(1)  # 礼貌限速


def _v(row: dict, key: str):
    cell = row.get(key)
    return cell["value"] if cell else None
