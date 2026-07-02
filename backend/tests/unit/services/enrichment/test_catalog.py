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


def test_categories_and_country_lang_parsed(tmp_path):
    from app.services.enrichment.catalog import MuseumCatalog

    p = tmp_path / "m.yaml"
    p.write_text(
        "museums:\n"
        "  orsay:\n"
        "    name_zh: 奥赛\n    name_en: Orsay\n    city_zh: 巴黎\n    city_en: Paris\n"
        "    country: FR\n    wikidata_qid: Q23402\n    category_filter: Q3305213\n"
        "    categories: [Q3305213, Q860861]\n    country_lang: fr\n"
        "    fetch_limit: 5\n    sample_size: 2\n",
        encoding="utf-8",
    )
    cfg = MuseumCatalog.from_file(p).get("orsay")
    assert cfg.categories == ["Q3305213", "Q860861"]
    assert cfg.country_lang == "fr"


def test_sources_parsed_from_yaml():
    # 上新馆=纯配置:每馆声明自己的补充源(法国馆才有 joconde)
    cfg = MuseumCatalog.from_file("museums.yaml").get("orsay")
    assert cfg.sources == ["joconde", "wikipedia"]


def test_sources_default_to_wikipedia(tmp_path):
    p = tmp_path / "m.yaml"
    p.write_text(
        "museums:\n  x:\n    name_zh: 馆\n    name_en: X\n    city_zh: 城\n"
        "    city_en: C\n    country: NL\n    wikidata_qid: Q1\n"
        "    category_filter: Q3305213\n    fetch_limit: 5\n    sample_size: 2\n",
        encoding="utf-8",
    )
    assert MuseumCatalog.from_file(p).get("x").sources == ["wikipedia"]


def test_categories_defaults_to_category_filter(tmp_path):
    from app.services.enrichment.catalog import MuseumCatalog

    p = tmp_path / "m.yaml"
    p.write_text(
        "museums:\n  orsay:\n    name_zh: 奥赛\n    name_en: Orsay\n    city_zh: 巴黎\n"
        "    city_en: Paris\n    country: FR\n    wikidata_qid: Q23402\n"
        "    category_filter: Q3305213\n    fetch_limit: 5\n    sample_size: 2\n",
        encoding="utf-8",
    )
    cfg = MuseumCatalog.from_file(p).get("orsay")
    assert cfg.categories == ["Q3305213"]
    assert cfg.country_lang is None
