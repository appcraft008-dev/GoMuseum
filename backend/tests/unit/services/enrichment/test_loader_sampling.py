from app.services.enrichment.loader import select_sample


def _objs():
    return [{"qid": f"Q{i}", "popularity": i} for i in range(10)]  # Q0..Q9，热度=i


def test_sample_takes_top_n_by_popularity():
    out = select_sample(_objs(), sample_size=3, sample_qids=[])
    assert {o["qid"] for o in out} == {"Q9", "Q8", "Q7"}


def test_sample_includes_fixed_qids_dedup():
    out = select_sample(_objs(), sample_size=2, sample_qids=["Q0"])
    qids = {o["qid"] for o in out}
    assert "Q0" in qids
    assert "Q9" in qids and "Q8" in qids
    assert len(out) == 3
