from app.services.enrichment.sources.base import ObjectContribution, Source


def test_contribution_holds_source_qid_fields_raw():
    c = ObjectContribution(
        source="wikidata", qid="Q1", fields={"year": "1866"}, raw={"x": 1}
    )
    assert c.source == "wikidata" and c.qid == "Q1"
    assert c.fields["year"] == "1866" and c.raw == {"x": 1}


def test_source_is_abstract():
    import inspect

    assert hasattr(Source, "fetch")
    assert inspect.isabstract(Source)


def test_source_enrich_default_returns_none():
    from app.services.enrichment.sources.base import Source

    class Spine(Source):
        name = "x"

        def fetch(self, cfg):
            return []

    assert Spine().enrich("Q1", {"P347": "REF"}, {}) is None
