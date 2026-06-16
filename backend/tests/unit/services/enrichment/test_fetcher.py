from app.services.enrichment.catalog import MuseumConfig
from app.services.enrichment.fetcher import Fetcher
from app.services.enrichment.sources.base import ObjectContribution

CFG = MuseumConfig(
    "orsay", "奥赛", "Orsay", "巴黎", "Paris", "FR", "Q23402", "Q3305213", 10, 5, []
)


class FakeSource:
    name = "wikidata"

    def fetch(self, cfg):
        yield ObjectContribution(
            "wikidata",
            "Q1",
            {"title_zh": "起源", "image_url": "http://x/a.jpg"},
            {"r": 1},
        )
        yield ObjectContribution("wikidata", "Q2", {"title_zh": "午餐"}, {"r": 2})


class FakeCatalog:
    def get(self, slug):
        return CFG


class FakePackStore:
    def __init__(self):
        self.saved = None

    def put(self, slug, pack):
        self.saved = pack
        return f"museum-packs/{slug}/X.json"


def test_fetch_builds_pack_with_museum_and_objects():
    ps = FakePackStore()
    f = Fetcher(catalog=FakeCatalog(), sources=[FakeSource()], pack_store=ps)
    key = f.fetch("orsay")
    assert key.endswith(".json")
    pack = ps.saved
    assert pack["museum"]["slug"] == "orsay" and pack["museum"]["qid"] == "Q23402"
    qids = {o["qid"] for o in pack["objects"]}
    assert qids == {"Q1", "Q2"}
    q1 = next(o for o in pack["objects"] if o["qid"] == "Q1")
    assert q1["title_zh"] == "起源"
    assert q1["image"]["source_url"] == "http://x/a.jpg"
    assert q1["sources"]["wikidata"]["raw"] == {"r": 1}
