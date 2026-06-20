from app.services.enrichment.sources.wikipedia import WikipediaSource


def test_enrich_pulls_extracts_for_en_and_country_lang():
    calls = []

    class FakeSession:
        def get_json(self, url, params=None, _transport=None):
            calls.append(url)
            lang = "fr" if "fr.wikipedia" in url else "en"
            return {"extract": f"extract-{lang}", "title": f"T-{lang}"}

    s = WikipediaSource(session=FakeSession())
    c = s.enrich(
        "Q1",
        {},
        {"wiki_titles": {"en": "Bedroom_in_Arles", "fr": "La_Chambre_à_Arles"}},
    )
    assert c is not None
    assert c.source == "wikipedia"
    assert c.fields["extract_en"] == "extract-en"
    assert c.fields["extract_fr"] == "extract-fr"
    assert any("en.wikipedia" in u for u in calls)
    assert any("fr.wikipedia" in u for u in calls)


def test_enrich_none_when_no_titles():
    assert WikipediaSource(session=None).enrich("Q1", {}, {}) is None


def test_enrich_skips_lang_without_extract():
    class FakeSession:
        def get_json(self, url, params=None, _transport=None):
            return {} if "fr.wikipedia" in url else {"extract": "ok"}

    c = WikipediaSource(session=FakeSession()).enrich(
        "Q1", {}, {"wiki_titles": {"en": "A", "fr": "B"}}
    )
    assert c.fields == {"extract_en": "ok"}  # fr 无 extract 被跳过
