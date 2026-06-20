from app.services.enrichment.registry import SourceRegistry


class FakeSource:
    def __init__(self, name, ext_pid=None):
        self.name = name
        self._ext_pid = ext_pid

    def probe(self, external_ids: dict) -> bool:
        return self._ext_pid is None or self._ext_pid in external_ids

    def fetch(self, cfg):
        return []


def test_registry_routes_by_external_id():
    wikidata = FakeSource("wikidata")  # 总适用
    joconde = FakeSource("joconde", ext_pid="P347")  # 需 P347
    reg = SourceRegistry([wikidata, joconde])

    has = reg.route({"P347": "000PE004070"})
    assert {s.name for s in has} == {"wikidata", "joconde"}

    without = reg.route({})
    assert {s.name for s in without} == {"wikidata"}


def test_registry_get_by_name():
    reg = SourceRegistry([FakeSource("wikidata")])
    assert reg.get("wikidata").name == "wikidata"
    assert reg.get("nope") is None
