"""JocondeSource：法国国家藏品库(data.culture.gouv.fr base-joconde-extrait)。
经 Wikidata P347 自动发现；提供权威法语一手事实（source=official）。"""

from __future__ import annotations

from app.services.enrichment.sources.base import ObjectContribution, Source

DATASET_URL = "https://data.culture.gouv.fr/api/records/1.0/search/"
DATASET = "base-joconde-extrait"


class JocondeSource(Source):
    name = "joconde"

    def __init__(self, session):
        self._session = session  # PoliteSession（注入，复用限速 + 便于测试）

    def probe(self, external_ids: dict) -> bool:
        return "P347" in external_ids

    def enrich(self, qid: str, external_ids: dict, context: dict):
        ref = external_ids.get("P347")
        if not ref:
            return None
        data = self._session.get_json(
            DATASET_URL, params={"dataset": DATASET, "q": ref, "rows": 1}
        )
        recs = data.get("records") or []
        if not recs:
            return None
        f = recs[0].get("fields", {})
        fields = {
            "title_fr": f.get("titre"),
            "artist_fr": f.get("auteur"),
            "medium_fr": f.get("materiaux_techniques"),
            "dimensions": f.get("mesures"),
            "inventory_number": f.get("numero_inventaire"),
            "provenance_fr": f.get("ancienne_appartenance"),
            "exhibitions_fr": f.get("exposition"),
            "bibliography_fr": f.get("bibliographie"),
            "subjects_fr": f.get("sujet_represente"),
            "period_fr": f.get("periode_de_creation"),
            "domaine_fr": f.get("domaine"),
            "denomination_fr": f.get("denomination"),
            "school_fr": f.get("ecole_pays"),
            "location_fr": f.get("localisation"),
        }
        return ObjectContribution(
            source="official", qid=qid, fields=fields, raw={"joconde": f}
        )

    def fetch(self, cfg):
        return []
