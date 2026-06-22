from app.services.enrichment.material import fetch_object_material
from app.services.enrichment.registry import SourceRegistry
from app.services.enrichment.sources.base import ObjectContribution, Source


class _FakeWiki(Source):
    name = "wikipedia"

    def fetch(self, cfg):
        return []

    def enrich(self, qid, external_ids, context):
        title = (context.get("wiki_titles") or {}).get("en")
        if not title:
            return None
        return ObjectContribution(
            source="wikipedia",
            qid=qid,
            fields={"extract_en": f"lead of {title}"},
            raw={},
        )


def test_fetch_object_material_returns_enrichment_attributes():
    reg = SourceRegistry([_FakeWiki()])
    out = fetch_object_material("Q1", {}, {"en": "The_Balcony"}, reg)
    assert out["extract_en"] == "lead of The_Balcony"
    # 身份/留痕键不进材料
    assert "qid" not in out and "sources" not in out and "external_ids" not in out


def test_fetch_object_material_empty_when_no_contribs():
    reg = SourceRegistry([_FakeWiki()])
    assert fetch_object_material("Q1", {}, {}, reg) == {}
