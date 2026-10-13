"""按 qid 补收录:catalog 同一条 SPARQL,只把「按馆藏列」换成「指定 qid」。"""

from scripts import add_works_by_qid as m


def test_query_targets_qids_and_fills_image_category(monkeypatch):
    seen = []

    def fake_sparql(q):
        seen.append(q)
        if len(seen) > 1:
            return []
        return [{"item": {"value": "http://www.wikidata.org/entity/Q140606109"},
                 "p31": {"value": "http://www.wikidata.org/entity/Q117052968"}}]  # fmt: skip

    monkeypatch.setattr(m._wd, "run_sparql", fake_sparql)
    cfg = m._catalog().get("orsay")  # 真配置:奥赛有 P31 白名单,指定 qid 时必须绕开
    [s] = m.stubs_for(cfg, ["Q140606109"], image="A b.jpg", category="sculpture")
    assert "VALUES ?item { wd:Q140606109 }" in seen[0]
    assert "wdt:P195" not in seen[0]
    assert "VALUES ?cat" not in seen[0]
    assert s.category == "sculpture"
    assert s.image_urls == [m._FILEPATH + "A%20b.jpg"]
