from app.services.enrichment.category_config import DEFAULT_CATEGORY, category_for


def test_known_qids_map():
    assert category_for("Q3305213") == "painting"
    assert category_for("Q860861") == "sculpture"
    assert category_for("Q125191") == "photograph"


def test_unknown_falls_back():
    assert category_for("Q999999") == DEFAULT_CATEGORY
    assert category_for(None) == DEFAULT_CATEGORY
