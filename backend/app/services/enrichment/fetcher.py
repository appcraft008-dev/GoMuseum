from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone

from app.services.enrichment.merge import merge_contributions


class Fetcher:
    def __init__(self, catalog, sources: list, pack_store):
        self._catalog = catalog
        self._sources = sources
        self._pack_store = pack_store

    def fetch(self, slug: str) -> str:
        cfg = self._catalog.get(slug)
        by_qid = defaultdict(list)
        for src in self._sources:
            for contrib in src.fetch(cfg):
                by_qid[contrib.qid].append(contrib)

        objects = []
        for qid, contribs in by_qid.items():
            merged = merge_contributions(contribs)
            image_url = merged.pop("image_url", None)
            obj = {
                "qid": qid,
                "category": merged.get("category", "painting"),
                "title_zh": merged.get("title_zh"),
                "title_en": merged.get("title_en"),
                "artist_zh": merged.get("artist_zh"),
                "artist_en": merged.get("artist_en"),
                "year": merged.get("year"),
                "period_zh": merged.get("period_zh"),
                "period_en": merged.get("period_en"),
                "inventory_number": merged.get("inventory_number"),
                "popularity": merged.get("popularity", 0),
                "attributes": merged.get("attributes", {}),
                "image": (
                    {"source_url": image_url, "license": None, "credit": None}
                    if image_url
                    else None
                ),
                "sources": merged["sources"],
            }
            objects.append(obj)

        pack = {
            "museum": {
                "slug": cfg.slug,
                "qid": cfg.wikidata_qid,
                "name_zh": cfg.name_zh,
                "name_en": cfg.name_en,
                "city_zh": cfg.city_zh,
                "city_en": cfg.city_en,
                "country": cfg.country,
            },
            "objects": objects,
            "fetched_at": datetime.now(timezone.utc).isoformat(),
            "source_versions": {s.name: "v1" for s in self._sources},
        }
        return self._pack_store.put(slug, pack)
