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
    categories=["Q3305213"],
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
    assert c.fields["category"] == "unknown"
    assert c.raw["item"]["value"].endswith("Q12418")


def test_category_not_derived_from_category_filter(monkeypatch):
    # category 现按 P31 映射，不再由 category_filter 决定；无 p31 → unknown
    sculpture_cfg = MuseumConfig(
        slug="x",
        name_zh="x",
        name_en="x",
        city_zh="x",
        city_en="x",
        country="FR",
        wikidata_qid="Q1",
        category_filter="Q860861",  # 雕塑
        fetch_limit=1,
        sample_size=1,
        sample_qids=[],
    )
    src = WikidataSource()
    monkeypatch.setattr(src, "_run_query", lambda sparql: FAKE_ROWS)
    monkeypatch.setattr(
        "app.services.enrichment.sources.wikidata.time.sleep", lambda s: None
    )
    out = list(src.fetch(sculpture_cfg))
    assert out[0].fields["category"] == "unknown"


def test_image_optional_and_external_ids_and_category(monkeypatch):
    rows = [
        {
            "item": {"value": "http://www.wikidata.org/entity/Q1"},
            "label_en": {"value": "A"},
            "links": {"value": "5"},
            "p31": {"value": "http://www.wikidata.org/entity/Q860861"},
            "joconde": {"value": "000PE004070"},
        }
    ]
    src = WikidataSource()
    monkeypatch.setattr(src, "_run_query", lambda sparql: rows)
    monkeypatch.setattr(
        "app.services.enrichment.sources.wikidata.time.sleep", lambda s: None
    )
    out = list(src.fetch(CFG))
    assert len(out) == 1
    c = out[0]
    assert c.fields["category"] == "sculpture"
    assert c.fields.get("image_url") is None
    assert c.fields["external_ids"] == {"P347": "000PE004070"}
