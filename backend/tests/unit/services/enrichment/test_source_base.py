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
