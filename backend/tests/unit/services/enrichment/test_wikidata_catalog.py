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
