from app.services.enrichment.catalog_source import CatalogSource, StubRecord


def test_stubrecord_fields_and_defaults():
    r = StubRecord(
        inventory_number="RF 2772",
        qid="Q775407",
        title="The Balcony",
        artist="Manet",
        year="1868",
        category="painting",
        image_url="http://x/a.jpg",
        popularity=12,
        owning_museum="orsay",
        source="wikidata",
    )
    assert r.qid == "Q775407" and r.owning_museum == "orsay"
    assert r.raw == {}


def test_catalogsource_is_abstract():
    import pytest

    with pytest.raises(TypeError):
        CatalogSource()
