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
    monkeypatch.setattr(mindex, "get_core", lambda ix: built.append(ix) or None)

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
