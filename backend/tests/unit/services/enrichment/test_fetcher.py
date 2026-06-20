from app.services.enrichment.catalog import MuseumConfig
from app.services.enrichment.fetcher import Fetcher
from app.services.enrichment.registry import SourceRegistry
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
    f = Fetcher(
        catalog=FakeCatalog(),
        spine=FakeSource(),
        registry=SourceRegistry([]),
        pack_store=ps,
    )
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


def test_two_phase_routes_enrichment_by_external_id():
    from app.services.enrichment.fetcher import Fetcher
    from app.services.enrichment.registry import SourceRegistry
    from app.services.enrichment.sources.base import ObjectContribution, Source

    class FakeSpine(Source):
        name = "wikidata"

        def fetch(self, cfg):
            yield ObjectContribution(
                source="wikidata",
                qid="Q1",
                fields={
                    "title_en": "A",
                    "external_ids": {"P347": "REF1"},
                    "popularity": 5,
                },
                raw={},
            )

    class FakeJoconde(Source):
        name = "joconde"

        def probe(self, external_ids):
            return "P347" in external_ids

        def enrich(self, qid, external_ids, context):
            return ObjectContribution(
                source="official",
                qid=qid,
                fields={"medium_fr": "huile"},
                raw={},
            )

        def fetch(self, cfg):
            return []

    class FakeStore:
        def __init__(self):
            self.pack = None

        def put(self, slug, pack):
            self.pack = pack
            return "key"

    store = FakeStore()
    f = Fetcher(
        catalog=FakeCatalog(),
        spine=FakeSpine(),
        registry=SourceRegistry([FakeJoconde()]),
        pack_store=store,
    )
    f.fetch("orsay")
    obj = store.pack["objects"][0]
    assert obj["qid"] == "Q1"
    assert obj["attributes"]["medium_fr"] == "huile"
    assert set(obj["sources"].keys()) >= {"wikidata", "official"}
