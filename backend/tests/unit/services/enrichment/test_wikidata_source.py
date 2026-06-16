from app.services.enrichment.catalog import MuseumConfig
from app.services.enrichment.sources.wikidata import WikidataSource

CFG = MuseumConfig(
    slug="orsay",
    name_zh="奥赛",
    name_en="Orsay",
    city_zh="巴黎",
    city_en="Paris",
    country="FR",
    wikidata_qid="Q23402",
    category_filter="Q3305213",
    fetch_limit=2,
    sample_size=2,
    sample_qids=[],
)

FAKE_ROWS = [
    {
        "item": {"value": "http://www.wikidata.org/entity/Q12418"},
        "label_zh": {"value": "蒙娜丽莎"},
        "label_en": {"value": "Mona Lisa"},
        "creator_zh": {"value": "达芬奇"},
        "year": {"value": "1503"},
        "image": {"value": "http://x/ml.jpg"},
        "links": {"value": "120"},
    },
]


def test_fetch_yields_contributions_with_qid_fields_raw(monkeypatch):
    src = WikidataSource()
    monkeypatch.setattr(src, "_run_query", lambda sparql: FAKE_ROWS)
    monkeypatch.setattr(
        "app.services.enrichment.sources.wikidata.time.sleep", lambda s: None
    )
    out = list(src.fetch(CFG))
    assert len(out) == 1
    c = out[0]
    assert c.source == "wikidata"
    assert c.qid == "Q12418"
    assert c.fields["title_zh"] == "蒙娜丽莎"
    assert c.fields["artist_zh"] == "达芬奇"
    assert c.fields["popularity"] == 120
    assert c.fields["category"] == "painting"
    assert c.raw["item"]["value"].endswith("Q12418")
