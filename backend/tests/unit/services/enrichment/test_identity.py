from app.services.enrichment.catalog_source import StubRecord
from app.services.enrichment.identity import merge_stubs


def _s(qid=None, inv=None, museum="orsay", source="wikidata", title="t"):
    return StubRecord(
        inventory_number=inv,
        qid=qid,
        title=title,
        artist=None,
        year=None,
        category="painting",
        image_url=None,
        popularity=None,
        owning_museum=museum,
        source=source,
    )


def test_merge_distinct_passthrough():
    recs = [_s(qid="Q1"), _s(qid="Q2")]
    assert [r.qid for r in merge_stubs(recs)] == ["Q1", "Q2"]


def test_merge_dedup_by_inventory_normalized():
    recs = [_s(inv="RF 2772", title="first"), _s(inv="rf-2772", title="second")]
    out = merge_stubs(recs)
    assert len(out) == 1 and out[0].title == "first"


def test_merge_dedup_by_qid():
    recs = [_s(qid="Q5", title="a"), _s(qid="Q5", title="b")]
    out = merge_stubs(recs)
    assert len(out) == 1 and out[0].title == "a"


def test_merge_inventory_namespaced_by_museum():
    recs = [_s(inv="RF 1", museum="orsay"), _s(inv="RF 1", museum="louvre")]
    assert len(merge_stubs(recs)) == 2
