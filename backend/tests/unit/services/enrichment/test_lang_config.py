from app.services.enrichment.lang_config import (
    DEFAULT_LANGUAGES,
    LANG_NAMES,
    resolve_languages,
)


def test_resolve_languages_defaults_when_no_override():
    assert resolve_languages() == DEFAULT_LANGUAGES
    assert resolve_languages(None) == DEFAULT_LANGUAGES
    assert resolve_languages([]) == DEFAULT_LANGUAGES


def test_resolve_languages_uses_override():
    assert resolve_languages(["en", "fr"]) == ["en", "fr"]


def test_default_languages_all_have_names():
    for code in DEFAULT_LANGUAGES:
        assert code in LANG_NAMES


def test_museum_config_has_languages_field_defaulting_empty():
    from app.services.enrichment.catalog import MuseumConfig

    cfg = MuseumConfig(
        slug="x",
        name_zh="x",
        name_en="x",
        city_zh="x",
        city_en="x",
        country="FR",
        wikidata_qid="Q1",
        category_filter="painting",
        fetch_limit=1,
        sample_size=1,
    )
    assert cfg.languages == []
