def test_fetch_rich_facts_maps_props_to_topics():
    from app.services.enrichment.evidence import fetch_rich_facts

    def fake_run_query(sparql):
        return [
            {"pid": {"value": "P88"}, "vLabel": {"value": "Khalil Bey"}},
            {"pid": {"value": "P180"}, "vLabel": {"value": "female nude"}},
            {"pid": {"value": "P135"}, "vLabel": {"value": "Realism"}},
        ]

    facts = fetch_rich_facts("Q1", run_query=fake_run_query)
    by = {f["source"]: f for f in facts}
    assert (
        by["wikidata:P88"]["value"] == "Khalil Bey"
        and by["wikidata:P88"]["topic"] == "background"
    )
    assert by["wikidata:P180"]["topic"] == "analysis"
    assert by["wikidata:P135"]["topic"] == "significance"


def test_fetch_rich_facts_empty_on_no_rows():
    from app.services.enrichment.evidence import fetch_rich_facts

    assert fetch_rich_facts("Q1", run_query=lambda s: []) == []
