from app.services.enrichment.sources.wikipedia import MAX_EXTRACT_CHARS, WikipediaSource


def _page(extract):
    return {"query": {"pages": {"123": {"extract": extract}}}}


def test_enrich_pulls_full_extracts_for_en_and_country_lang():
    calls = []

    class FakeSession:
        def get_json(self, url, params=None, _transport=None):
            calls.append((url, params))
            lang = "fr" if "fr.wikipedia" in url else "en"
            return _page(f"full-{lang}")

    s = WikipediaSource(session=FakeSession())
    c = s.enrich(
        "Q1",
        {},
        {"wiki_titles": {"en": "Bedroom_in_Arles", "fr": "La_Chambre_à_Arles"}},
    )
    assert c is not None and c.source == "wikipedia"
    assert c.fields["extract_en"] == "full-en"
    assert c.fields["extract_fr"] == "full-fr"
    # 用 Action API：prop=extracts + explaintext，标题经 params 传
    url0, params0 = calls[0]
    assert "/w/api.php" in url0
    assert params0["prop"] == "extracts" and params0["explaintext"] == 1
    assert params0["titles"] in ("Bedroom_in_Arles", "La_Chambre_à_Arles")


def test_enrich_truncates_to_max_chars():
    long = "x" * (MAX_EXTRACT_CHARS + 500)

    class FakeSession:
        def get_json(self, url, params=None, _transport=None):
            return {"query": {"pages": {"1": {"extract": long}}}}

    c = WikipediaSource(session=FakeSession()).enrich(
        "Q1", {}, {"wiki_titles": {"en": "A"}}
    )
    assert len(c.fields["extract_en"]) == MAX_EXTRACT_CHARS


def test_enrich_none_when_no_titles():
    assert WikipediaSource(session=None).enrich("Q1", {}, {}) is None


def test_enrich_skips_lang_without_extract():
    class FakeSession:
        def get_json(self, url, params=None, _transport=None):
            # fr 页缺失（missing page 无 extract）
            if "fr.wikipedia" in url:
                return {"query": {"pages": {"-1": {}}}}
            return {"query": {"pages": {"5": {"extract": "ok"}}}}

    c = WikipediaSource(session=FakeSession()).enrich(
        "Q1", {}, {"wiki_titles": {"en": "A", "fr": "B"}}
    )
    assert c.fields == {"extract_en": "ok"}
