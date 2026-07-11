from app.services.enrichment.sources.wikidata_catalog import WikidataCatalog


class _Cfg:
    slug = "orsay"
    wikidata_qid = "Q23402"
    categories = ["Q3305213"]
    category_filter = "Q3305213"
    country_lang = "fr"
    fetch_limit = 200


def _row(qid, title, links, inv=None, p31="Q3305213"):
    cell = lambda v: {"value": v}
    r = {
        "item": cell(f"http://www.wikidata.org/entity/{qid}"),
        "label_en": cell(title),
        "creator_en": cell("Manet"),
        "year": cell("1868"),
        "links": cell(str(links)),
        "p31": cell(f"http://www.wikidata.org/entity/{p31}"),
    }
    if inv:
        r["inventory"] = cell(inv)
    return r


def test_wikidata_catalog_lists_stubrecords():
    rows = [_row("Q775407", "The Balcony", 12, inv="RF 2772")]
    cat = WikidataCatalog(run_query=lambda sparql: rows)
    out = list(cat.list(_Cfg()))
    assert len(out) == 1
    s = out[0]
    assert s.qid == "Q775407" and s.title == "The Balcony"
    assert s.artist == "Manet" and s.year == "1868"
    assert s.inventory_number == "RF 2772"
    assert s.popularity == 12 and s.category == "painting"
    assert s.owning_museum == "orsay" and s.source == "wikidata"


def test_wikidata_catalog_dedups_and_stops_on_empty_page():
    page1 = [_row("Q1", "A", 5), _row("Q1", "A", 5)]
    calls = {"n": 0}

    def fake(sparql):
        calls["n"] += 1
        return page1 if calls["n"] == 1 else []

    cat = WikidataCatalog(run_query=fake)
    out = list(cat.list(_Cfg()))
    assert [s.qid for s in out] == ["Q1"]


def test_wikidata_catalog_extracts_routing():
    cell = lambda v: {"value": v}
    row = _row("Q775407", "The Balcony", 12, inv="RF 2772")
    row["joconde"] = cell("000PE026604")
    row["sitelink_en"] = cell("https://en.wikipedia.org/wiki/The_Balcony")
    row["sitelink_cl"] = cell("https://fr.wikipedia.org/wiki/Le_Balcon")
    cat = WikidataCatalog(run_query=lambda sparql: [row])
    s = list(cat.list(_Cfg()))[0]
    assert s.external_ids == {"P347": "000PE026604"}
    assert s.wiki_titles == {"en": "The_Balcony", "fr": "Le_Balcon"}


def test_wikidata_catalog_routing_empty_when_absent():
    cat = WikidataCatalog(run_query=lambda sparql: [_row("Q1", "A", 5)])
    s = list(cat.list(_Cfg()))[0]
    assert s.external_ids == {} and s.wiki_titles == {}


def test_wikidata_catalog_query_requires_image():
    # 收录策略:有图才收录(识别参照+合规前提)→ SPARQL P18 必填,不再 OPTIONAL
    seen = {}

    def fake(sparql):
        seen["sparql"] = sparql
        return []

    list(WikidataCatalog(run_query=fake).list(_Cfg()))
    assert "OPTIONAL {{ ?item wdt:P18" not in seen["sparql"].replace("{ ?", "{{ ?")
    assert "?item wdt:P18 ?image ." in seen["sparql"]


def test_wikidata_catalog_upgrades_category_on_multi_p31():
    # 多 P31 作品(如 油画+习作):已知类目优先于 unknown,不受行序影响
    rows = [
        _row("Q1", "A", 5, p31="Q999999"),  # 未知类型行先到 → unknown
        _row("Q1", "A", 5, p31="Q3305213"),  # 同件的绘画行后到 → 应升级
    ]
    calls = {"n": 0}

    def fake(sparql):
        calls["n"] += 1
        return rows if calls["n"] == 1 else []

    out = list(WikidataCatalog(run_query=fake).list(_Cfg()))
    assert len(out) == 1
    assert out[0].category == "painting"


def test_wikidata_catalog_collects_all_p18_images():
    # 收录策略:P18 全收(雕塑多角度参照);首张=image_url,全部进 image_urls
    rows = [
        _row("Q1", "A", 5),
        _row("Q1", "A", 5),
    ]
    rows[0]["image"] = {"value": "http://img/a.jpg"}
    rows[1]["image"] = {"value": "http://img/b.jpg"}
    calls = {"n": 0}

    def fake(sparql):
        calls["n"] += 1
        return rows if calls["n"] == 1 else []

    out = list(WikidataCatalog(run_query=fake).list(_Cfg()))
    assert len(out) == 1
    assert out[0].image_url == "http://img/a.jpg"
    assert out[0].image_urls == ["http://img/a.jpg", "http://img/b.jpg"]


def test_wikidata_catalog_retries_empty_page_before_stop():
    """空页≠到底:WDQS 深 OFFSET 超时返回空——重试后有数据则继续收。"""
    calls = {"n": 0}

    def fake(sparql):
        calls["n"] += 1
        # 页1有数据 → 页2空(模拟超时) → 页3重试拿到数据 → 之后一直空(真到底)
        if calls["n"] == 1:
            return [_row("Q1", "A", 5)]
        if calls["n"] == 3:
            return [_row("Q2", "B", 3)]
        return []

    out = list(WikidataCatalog(run_query=fake).list(_Cfg()))
    assert {r.qid for r in out} == {"Q1", "Q2"}  # 空页重试后仍收到 Q2
    assert calls["n"] >= 5  # 页2空+重试, 尾部空页也要连空3次才停
