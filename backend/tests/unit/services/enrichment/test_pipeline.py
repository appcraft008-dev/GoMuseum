from types import SimpleNamespace

from app.services.enrichment.pipeline import _facts_text, _row_to_obj


def test_row_to_obj_maps_columns_and_attributes():
    o = SimpleNamespace(
        title_en="Olympia",
        artist_en="Manet",
        year="1863",
        category="painting",
        attributes={"extract_en": "lead text"},
    )
    obj = _row_to_obj(o)
    assert obj["title_en"] == "Olympia"
    assert obj["category"] == "painting"
    assert obj["attributes"]["extract_en"] == "lead text"


def test_row_to_obj_handles_none_attributes():
    o = SimpleNamespace(
        title_en="X", artist_en=None, year=None, category="painting", attributes=None
    )
    assert _row_to_obj(o)["attributes"] == {}


def test_facts_text_lists_present_hard_facts_only():
    obj = {"title_en": "Olympia", "artist_en": "Manet", "year": "1863"}
    facts = _facts_text(obj)
    assert "- Title: Olympia" in facts
    assert "- Artist: Manet" in facts
    assert "- Year: 1863" in facts


def test_facts_text_skips_missing():
    facts = _facts_text({"title_en": "Olympia", "artist_en": None, "year": None})
    assert facts == "- Title: Olympia"
