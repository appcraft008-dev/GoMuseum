import pytest

from app.services.enrichment.catalog import MuseumCatalog, MuseumConfig


def test_get_returns_typed_config():
    cat = MuseumCatalog.from_file("museums.yaml")
    cfg = cat.get("orsay")
    assert isinstance(cfg, MuseumConfig)
    assert cfg.slug == "orsay"
    assert cfg.wikidata_qid == "Q23402"
    assert cfg.sample_size == 30
    assert cfg.sample_qids == []


def test_unknown_slug_raises():
    cat = MuseumCatalog.from_file("museums.yaml")
    with pytest.raises(KeyError):
        cat.get("nope")
