from app.services.enrichment.content_enricher import build_material


def test_build_material_includes_facts_and_wikipedia():
    obj = {
        "qid": "Q1",
        "title_en": "Bedroom in Arles",
        "artist_en": "Vincent van Gogh",
        "year": "1889",
        "category": "painting",
        "attributes": {
            "medium_fr": "huile sur toile",
            "dimensions": "73 × 92 cm",
            "extract_en": "Van Gogh painted his bedroom in Arles in 1888.",
        },
    }
    mat = build_material(obj)
    assert "Bedroom in Arles" in mat
    assert "Vincent van Gogh" in mat
    assert "huile sur toile" in mat
    assert "Van Gogh painted his bedroom" in mat


def test_build_material_empty_when_no_facts():
    mat = build_material({"qid": "Q1", "category": "painting", "attributes": {}})
    assert isinstance(mat, str)
