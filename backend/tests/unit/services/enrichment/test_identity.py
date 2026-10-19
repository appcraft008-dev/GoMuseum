from app.services.enrichment.catalog_source import StubRecord
from app.services.enrichment.identity import merge_stubs


def _s(qid=None, inv=None, museum="orsay", source="wikidata", title="t", cre=None):
    return StubRecord(
        raw={"creator_qids": cre} if cre else {},
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


def test_same_inventory_different_creators_are_two_works():
    """奥赛油画/雕塑两套 RF 编号撞号:同号、作者毫无交集 = 两件不同作品,都留。"""
    recs = [
        _s(qid="Q17491121", inv="RF 166", cre=["Q553571"]),
        _s(qid="Q76465029", inv="RF 166", cre=["Q654201"]),
    ]
    assert [r.qid for r in merge_stubs(recs)] == ["Q17491121", "Q76465029"]


def test_same_inventory_shared_creator_is_wikidata_duplicate():
    """同号且作者有交集(含合作者多一位)= Wikidata 重复条目/正反面,仍首条胜。"""
    recs = [
        _s(qid="Q50401180", inv="PPS1145", cre=["Q30755", "Q3371526"]),
        _s(qid="Q106461104", inv="PPS1145", cre=["Q30755"]),
    ]
    assert [r.qid for r in merge_stubs(recs)] == ["Q50401180"]


def test_same_inventory_unknown_creator_still_deduped():
    recs = [_s(qid="Q1", inv="RF 9", cre=["Q7"]), _s(qid="Q2", inv="RF 9")]
    assert [r.qid for r in merge_stubs(recs)] == ["Q1"]
