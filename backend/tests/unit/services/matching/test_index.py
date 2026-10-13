from app.services.matching import index as mindex
from app.services.search import inprocess


def _e(i, names, artists=()):
    return {
        "id": i,
        "qid": f"Q{i}",
        "museum_id": 1 if i < 3 else 2,
        "names": set(names),
        "artists": set(artists),
    }


def _idx():
    return [
        _e(0, {"the starry night"}, {"vincent van gogh"}),
        _e(1, {"starry night over the rhone"}, {"vincent van gogh"}),
        _e(2, {"water lilies"}, {"claude monet"}),
        _e(3, {"le radeau de la meduse"}, {"theodore gericault"}),
    ]


def test_and_hits_requires_every_token():
    core = mindex.get_core(_idx())
    hits = core.and_hits(["gogh", "rhone"], None)
    assert set(hits) == {1}


def test_typo_expands_with_osa():
    core = mindex.get_core(_idx())
    assert "starry" in core.expand("satrry", "title")  # 相邻颠倒=1 次编辑


def test_last_token_prefix():
    core = mindex.get_core(_idx())
    assert set(core.and_hits(["water", "lil"], None)) == {2}


def test_core_for_filtered_list_reuses_global_core(monkeypatch):
    g = _idx()
    monkeypatch.setattr(inprocess, "_index_cache", {None: (0.0, g)})
    gcore = mindex.get_core(g)
    scoped = [e for e in g if e["museum_id"] == 1]
    core, allowed = mindex.core_for(scoped)
    assert core is gcore and allowed == {0, 1, 2}
    core2, allowed2 = mindex.core_for(g)
    assert core2 is gcore and allowed2 is None


def test_refresh_builds_core_in_background(monkeypatch):
    built = []
    monkeypatch.setattr(inprocess, "_index_cache", {})  # 测完还原,不污染别的用例
    monkeypatch.setattr(inprocess, "_build_global", lambda db: _idx())
    monkeypatch.setattr(mindex, "get_core", lambda ix, **kw: built.append(ix) or None)

    class _T:
        def __init__(self, target, **kw):
            self.t = target

        def start(self):
            self.t()

    monkeypatch.setattr(inprocess.threading, "Thread", _T)
    monkeypatch.setattr(
        "app.core.database.SessionLocal",
        lambda: type("S", (), {"close": lambda s: None})(),
    )
    monkeypatch.setattr(inprocess, "_refreshing", False)
    inprocess._refresh_index_async()
    assert built and built[0] is inprocess._index_cache[None][1]


def test_token_in_every_entry_still_counts_as_hit():
    # 每件都有的词 idf=0,权重 0 也算命中;否则「每词都中」整体落空
    core = mindex.get_core(_idx()[:2])  # 两件都是 van gogh
    assert set(core.and_hits(["gogh", "rhone"], None)) == {1}


def test_pinned_global_core_survives_adhoc_cores(monkeypatch):
    # 刷新竞态时子集会单建临时倒排;它们不能把全局倒排挤出缓存(否则下个请求重建 4.5s)
    built = []
    orig = mindex.Core
    monkeypatch.setattr(mindex, "Core", lambda ix: built.append(1) or orig(ix))
    g = _idx()
    gcore = mindex.get_core(g, pin=True)
    for _ in range(3):
        mindex.get_core([_e(9, {"x"})])  # 3 个临时核
    n = len(built)
    assert mindex.get_core(g) is gcore and len(built) == n


def _brute_substr(idx, field, q):
    """旧语义:逐件 `q in n`,前缀=任一名字 startswith。"""
    return {
        i: any(n.startswith(q) for n in e[field])
        for i, e in enumerate(idx)
        if any(q in n for n in e[field])
    }


def test_substr_matches_brute_force():
    idx = _idx() + [
        _e(4, {"nympheas", "les nympheas bleus", "nuit etoilee"}, {"claude monet"}),
        _e(5, {"星夜", "夜"}, {"梵高"}),
    ]
    core = mindex.Core(idx)
    qs = ["s", "st", "starry", "night", "the", "n", "e", "ympheas", "nuit", "zz",
          "y o", "夜", "星夜", "梵", "monet", "gogh", "o"]  # fmt: skip
    for q in qs:
        assert core.substr("title", q) == _brute_substr(idx, "names", q), q
        assert core.substr("artist", q) == _brute_substr(idx, "artists", q), q


def test_expand_length_buckets_match_full_vocab_scan():
    from rapidfuzz import process
    from rapidfuzz.distance import OSA

    idx = _idx() + [
        _e(4, {"starr starrs stary starryy sterry statry nght nightt knight"}),
    ]
    core = mindex.Core(idx)
    for tok in ["starry", "satrry", "night", "nihgt", "meduse", "gericault"]:
        k = 1 if len(tok) < 7 else 2
        want = {
            v: 1 - d / max(len(tok), len(v))
            for v, d, _ in process.extract(
                tok, core.vocab["title"], scorer=OSA.distance, score_cutoff=k, limit=8
            )
        }
        got = core.expand(tok, "title")
        got.pop(tok, None)
        want.pop(tok, None)
        assert got == want, tok
