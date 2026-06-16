from app.services.enrichment.merge import merge_contributions
from app.services.enrichment.sources.base import ObjectContribution


def test_single_source_projects_fields_and_raw():
    c = ObjectContribution(
        "wikidata", "Q1", {"year": "1866", "title_zh": "起源"}, {"r": 1}
    )
    out = merge_contributions([c])
    assert out["qid"] == "Q1"
    assert out["year"] == "1866"
    assert out["sources"]["wikidata"]["raw"] == {"r": 1}
    assert "fetched_at" in out["sources"]["wikidata"]


def test_precedence_higher_source_wins_per_field():
    wiki = ObjectContribution("wikidata", "Q1", {"year": "1866", "title_zh": "A"}, {})
    manual = ObjectContribution("manual", "Q1", {"year": "1865"}, {})
    out = merge_contributions([wiki, manual])  # 默认 manual > wikidata
    assert out["year"] == "1865"
    assert out["title_zh"] == "A"
    assert set(out["sources"].keys()) == {"wikidata", "manual"}
