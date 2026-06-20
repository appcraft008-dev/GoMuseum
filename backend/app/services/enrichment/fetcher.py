from __future__ import annotations

from datetime import datetime, timezone

from app.services.enrichment.merge import merge_contributions

_CORE = {
    "qid",
    "category",
    "title_zh",
    "title_en",
    "artist_zh",
    "artist_en",
    "year",
    "inventory_number",
    "popularity",
    "sources",
    "_conflicts",
    "external_ids",
}


class Fetcher:
    def __init__(self, catalog, spine, registry, pack_store):
        self._catalog = catalog
        self._spine = spine
        self._registry = registry
        self._pack_store = pack_store

    def fetch(self, slug: str) -> str:
        cfg = self._catalog.get(slug)
        objects = []
        for spine_contrib in self._spine.fetch(cfg):
            qid = spine_contrib.qid
            ext = spine_contrib.fields.get("external_ids", {}) or {}
            contribs = [spine_contrib]
            for src in self._registry.route(ext):
                c = src.enrich(qid, ext, {})
                if c is not None:
                    contribs.append(c)
            merged = merge_contributions(contribs)
            image_url = merged.pop("image_url", None)
            objects.append(
                {
                    "qid": qid,
                    "category": merged.get("category", "unknown"),
                    "title_zh": merged.get("title_zh"),
                    "title_en": merged.get("title_en"),
                    "artist_zh": merged.get("artist_zh"),
                    "artist_en": merged.get("artist_en"),
                    "year": merged.get("year"),
                    "inventory_number": merged.get("inventory_number"),
                    "popularity": merged.get("popularity", 0),
                    "attributes": {k: v for k, v in merged.items() if k not in _CORE},
                    "external_ids": ext,
                    "image": (
                        {"source_url": image_url, "license": None, "credit": None}
                        if image_url
                        else None
                    ),
                    "needs_review": bool(merged.get("_conflicts")),
                    "sources": merged["sources"],
                }
            )
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
        }
        return self._pack_store.put(slug, pack)
