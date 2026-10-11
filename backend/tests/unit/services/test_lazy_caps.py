"""懒生成每账号/每 IP 日上限(spec 2026-10-11 方案 A)。"""

import threading

import fakeredis
import pytest

from app.services.enrichment import lazy
from app.services.enrichment.lazy import (
    CAP_PER_IP,
    CAP_PER_USER,
    WEIGHT_GENERATION,
    _charge,
)


@pytest.fixture()
def r():
    return fakeredis.FakeRedis(decode_responses=True)


def _used(r, layer, ident):
    keys = r.keys(f"lazy:{layer}:{ident}:*")
    return int(r.get(keys[0])) if keys else 0


def test_under_cap_passes_and_counts_both_layers(r):
    assert _charge("u1", "1.2.3.4", 8, redis=r) is None
    assert _used(r, "u", "u1") == 8
    assert _used(r, "ip", "1.2.3.4") == 8
    assert 0 < r.ttl(r.keys("lazy:u:u1:*")[0]) <= 172800


def test_user_cap_blocks_and_rolls_back_both(r):
    for _ in range(CAP_PER_USER // WEIGHT_GENERATION):  # 20 次 = 160 段,正好到线
        assert _charge("u1", "1.2.3.4", 8, redis=r) is None
    assert _charge("u1", "1.2.3.4", 8, redis=r) == "user"
    assert _used(r, "u", "u1") == CAP_PER_USER  # 被拒那次已回滚
    assert _used(r, "ip", "1.2.3.4") == CAP_PER_USER  # 另一层也回滚


def test_ip_cap_blocks_across_accounts(r):
    n = 0
    while _charge(f"u{n}", "9.9.9.9", 8, redis=r) is None:  # 换号同 IP
        n += 1
    assert n == CAP_PER_IP // WEIGHT_GENERATION  # 37 件
    assert _used(r, "ip", "9.9.9.9") <= CAP_PER_IP
    assert _used(r, "u", f"u{n}") == 0  # 被拒账号的计数已回滚


def test_translation_weight_is_lighter(r):
    for _ in range(CAP_PER_USER // 3):  # 53 次翻译
        assert _charge("u1", "1.2.3.4", 3, redis=r) is None
    assert _charge("u1", "1.2.3.4", 3, redis=r) == "user"


def test_missing_ip_only_counts_user(r):
    assert _charge("u1", None, 8, redis=r) is None
    assert r.keys("lazy:ip:*") == []


def test_redis_unavailable_fails_open(monkeypatch):
    monkeypatch.setattr(lazy, "_redis", lambda: None)
    assert _charge("u1", "1.2.3.4", 8) is None


def test_redis_error_fails_open():
    class Boom:
        def pipeline(self):
            raise ConnectionError("down")

    assert _charge("u1", "1.2.3.4", 8, redis=Boom()) is None


def test_keys_are_per_utc_day(r, monkeypatch):
    from datetime import datetime, timezone

    class D:
        @staticmethod
        def now(tz=None):
            return datetime(2026, 10, 11, 23, 59, tzinfo=timezone.utc)

    monkeypatch.setattr(lazy, "datetime", D)
    _charge("u1", None, 8, redis=r)
    D.now = staticmethod(
        lambda tz=None: datetime(2026, 10, 12, 0, 1, tzinfo=timezone.utc)
    )
    _charge("u1", None, 8, redis=r)
    assert sorted(r.keys("lazy:u:u1:*")) == ["lazy:u:u1:20261011", "lazy:u:u1:20261012"]


def test_concurrent_charges_never_exceed_cap(r):
    r.set("lazy:u:u1:" + lazy._today(), CAP_PER_USER - 8)  # 只剩一次的额度
    results = []
    barrier = threading.Barrier(2)

    def go():
        barrier.wait()
        results.append(_charge("u1", None, 8, redis=r))

    ts = [threading.Thread(target=go) for _ in range(2)]
    [t.start() for t in ts]
    [t.join() for t in ts]
    assert sorted(results, key=str) == [None, "user"]
    assert _used(r, "u", "u1") == CAP_PER_USER
