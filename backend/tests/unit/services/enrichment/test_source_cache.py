from app.services.enrichment.source_cache import SourceCache


class FakeStorage:
    def __init__(self):
        self.objects = {}

    def put(self, key, data, content_type):
        self.objects[key] = data

    def get(self, key):
        return self.objects.get(key)

    def exists(self, key):
        return key in self.objects


def test_cache_miss_calls_fetch_then_hit_reuses():
    storage = FakeStorage()
    cache = SourceCache(storage, day="2026-06-20")
    calls = {"n": 0}

    def fetch():
        calls["n"] += 1
        return {"v": 42}

    a = cache.get_or_fetch("wikipedia", "Q1", fetch)
    b = cache.get_or_fetch("wikipedia", "Q1", fetch)
    assert a == b == {"v": 42}
    assert calls["n"] == 1  # 第二次命中缓存,不再 fetch


def test_cache_key_includes_source_and_day():
    storage = FakeStorage()
    SourceCache(storage, day="2026-06-20").get_or_fetch(
        "joconde", "REF9", lambda: {"x": 1}
    )
    assert any(
        "joconde" in k and "REF9" in k and "2026-06-20" in k for k in storage.objects
    )
