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


def test_precedence_param_official_beats_wikidata():
    from app.services.enrichment.sources.base import ObjectContribution

    wd = ObjectContribution(source="wikidata", qid="Q1", fields={"medium": "oil"})
    jo = ObjectContribution(
        source="official", qid="Q1", fields={"medium": "huile sur toile"}
    )
    merged = merge_contributions(
        [wd, jo], precedence=["wikidata", "official", "manual"]
    )
    assert merged["medium"] == "huile sur toile"


def test_non_empty_higher_wins_empty_does_not_overwrite():
    from app.services.enrichment.sources.base import ObjectContribution

    wd = ObjectContribution(source="wikidata", qid="Q1", fields={"medium": "oil"})
    jo = ObjectContribution(source="official", qid="Q1", fields={"medium": None})
    merged = merge_contributions(
        [wd, jo], precedence=["wikidata", "official", "manual"]
    )
    assert merged["medium"] == "oil"


def test_same_rank_conflict_recorded_not_silent():
    from app.services.enrichment.sources.base import ObjectContribution

    a = ObjectContribution(source="official", qid="Q1", fields={"medium": "huile"})
    b = ObjectContribution(source="official", qid="Q1", fields={"medium": "tempera"})
    merged = merge_contributions([a, b], precedence=["wikidata", "official", "manual"])
    assert "_conflicts" in merged
    assert any(c["field"] == "medium" for c in merged["_conflicts"])


def test_no_conflict_when_values_agree():
    from app.services.enrichment.sources.base import ObjectContribution

    a = ObjectContribution(source="official", qid="Q1", fields={"medium": "huile"})
    b = ObjectContribution(source="official", qid="Q1", fields={"medium": "huile"})
    merged = merge_contributions([a, b], precedence=["wikidata", "official", "manual"])
    assert not merged.get("_conflicts")
