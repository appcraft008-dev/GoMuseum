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


def test_stubrecord_carries_routing_info():
    from app.services.enrichment.catalog_source import StubRecord

    s = StubRecord(
        inventory_number="RF 2772",
        qid="Q1",
        title="T",
        artist="A",
        year="1868",
        category="painting",
        image_url=None,
        popularity=3,
        owning_museum="orsay",
        source="wikidata",
        external_ids={"P347": "000PE026604"},
        wiki_titles={"en": "The_Balcony"},
    )
    assert s.external_ids == {"P347": "000PE026604"}
    assert s.wiki_titles == {"en": "The_Balcony"}


def test_stubrecord_routing_defaults_empty():
    from app.services.enrichment.catalog_source import StubRecord

    s = StubRecord(
        inventory_number=None,
        qid="Q1",
        title="T",
        artist=None,
        year=None,
        category=None,
        image_url=None,
        popularity=None,
        owning_museum="orsay",
        source="wikidata",
    )
    assert s.external_ids == {} and s.wiki_titles == {}
