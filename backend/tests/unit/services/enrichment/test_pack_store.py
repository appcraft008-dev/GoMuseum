from app.services.enrichment.pack_store import PackStore


class FakeStorage:
    def __init__(self):
        self.blobs = {}

    def put(self, key, data, content_type):
        self.blobs[key] = data

    def get(self, key):
        return self.blobs.get(key)


def test_put_returns_versioned_key_and_get_roundtrips():
    st = FakeStorage()
    ps = PackStore(st)
    pack = {"museum": {"slug": "orsay"}, "objects": [{"qid": "Q1"}]}
    key = ps.put("orsay", pack)
    assert key.startswith("museum-packs/orsay/") and key.endswith(".json")
    assert ps.get(key) == pack


def test_latest_key_picks_most_recent():
    st = FakeStorage()
    ps = PackStore(st)
    k1 = ps.put("orsay", {"a": 1})
    k2 = ps.put("orsay", {"a": 2})
    assert ps.latest_key("orsay", listing=[k1, k2]) == max(k1, k2)
