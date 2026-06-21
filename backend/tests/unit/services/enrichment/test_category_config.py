from app.services.enrichment.category_config import DEFAULT_CATEGORY, category_for


def test_known_qids_map():
    assert category_for("Q3305213") == "painting"
    assert category_for("Q860861") == "sculpture"
    assert category_for("Q125191") == "photograph"


def test_unknown_falls_back():
    assert category_for("Q999999") == DEFAULT_CATEGORY
    assert category_for(None) == DEFAULT_CATEGORY


def test_sections_by_category_and_fallback():
    from app.services.enrichment.category_config import sections_for

    assert sections_for("painting") == [
        "overview",
        "artist",
        "background",
        "analysis",
        "significance",
        "facts",
    ]
    assert sections_for("sculpture")[:3] == ["overview", "artist", "material-technique"]
    assert sections_for("unknown") == [
        "overview",
        "background",
        "significance",
        "facts",
    ]


def test_section_label_localized_with_en_fallback():
    from app.services.enrichment.category_config import section_label

    assert section_label("overview", "zh") == "通用描述"
    assert section_label("overview", "en") == "Overview"
    assert section_label("overview", "fr") == "Aperçu"
    assert section_label("overview", "xx") == "Overview"
