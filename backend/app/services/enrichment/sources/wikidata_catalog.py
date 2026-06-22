"""WikidataCatalog：用现有 Wikidata SPARQL 主干列对象、产 StubRecord。
复用 wikidata.QUERY/_v/_PAGE；run_query 注入式（默认真实 SPARQL）。spec §4。
注：现有 WikidataSource.fetch 保留不动；Phase B 才让 Fetcher 改用本类。"""

from __future__ import annotations

import time
from typing import Iterable

import requests

from app.services.enrichment.catalog_source import CatalogSource, StubRecord
from app.services.enrichment.category_config import category_for
from app.services.enrichment.sources import wikidata as _wd


def _default_run_query(sparql: str) -> list[dict]:
    r = requests.get(
        _wd.SPARQL_ENDPOINT,
        params={"query": sparql, "format": "json"},
        headers={
            "User-Agent": _wd.USER_AGENT,
            "Accept": "application/sparql-results+json",
        },
        timeout=60,
    )
    r.raise_for_status()
    return r.json()["results"]["bindings"]


class WikidataCatalog(CatalogSource):
    name = "wikidata"

    def __init__(self, run_query=None):
        self._run_query = run_query or _default_run_query

    def list(self, cfg) -> Iterable[StubRecord]:
        cats = cfg.categories or [cfg.category_filter]
        cat_values = " ".join(f"wd:{q}" for q in cats)
        seen: set[str] = set()
        fetched = 0
        offset = 0
        while fetched < cfg.fetch_limit:
            page = min(_wd._PAGE, cfg.fetch_limit - fetched)
            rows = self._run_query(
                _wd.QUERY.format(
                    museum=cfg.wikidata_qid,
                    cat_values=cat_values,
                    country_lang=(cfg.country_lang or "fr"),
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
                p31 = (row.get("p31", {}) or {}).get("value", "").rsplit("/", 1)[-1]
                ext = {}
                jo = _wd._v(row, "joconde")
                if jo:
                    ext["P347"] = jo
                titles = {}
                se = _wd._v(row, "sitelink_en")
                if se:
                    titles["en"] = se.rsplit("/", 1)[-1]
                scl = _wd._v(row, "sitelink_cl")
                if scl:
                    titles[cfg.country_lang or "fr"] = scl.rsplit("/", 1)[-1]
                yield StubRecord(
                    inventory_number=_wd._v(row, "inventory"),
                    qid=qid,
                    title=_wd._v(row, "label_en"),
                    artist=_wd._v(row, "creator_en"),
                    year=_wd._v(row, "year"),
                    category=category_for(p31),
                    image_url=_wd._v(row, "image"),
                    popularity=int(_wd._v(row, "links") or 0),
                    owning_museum=cfg.slug,
                    source="wikidata",
                    raw=row,
                    external_ids=ext,
                    wiki_titles=titles,
                )
            fetched += len(rows)
            offset += len(rows)
            if self._run_query is _default_run_query:
                time.sleep(1)
