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


def test_redis_unavailable_fails_open_and_alerts(monkeypatch):
    sent = []
    monkeypatch.setattr(lazy.ops_alert, "alert_throttled", lambda k, *a: sent.append(k))
    monkeypatch.setattr(lazy, "_redis", lambda: None)
    assert _charge("u1", "1.2.3.4", 8) is None
    assert sent == ["lazy-caps-redis"]


def test_redis_error_fails_open_and_alerts(monkeypatch):
    sent = []
    monkeypatch.setattr(lazy.ops_alert, "alert_throttled", lambda k, *a: sent.append(k))

    class Boom:
        def pipeline(self):
            raise ConnectionError("down")

    assert _charge("u1", "1.2.3.4", 8, redis=Boom()) is None
    assert sent == ["lazy-caps-redis"]


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


def test_rollback_failure_still_refuses(r):
    """已知超限、但退回额度那一步 Redis 报错 → 仍然拒绝(不能因为退不回去就放行)。"""
    r.set("lazy:u:u1:" + lazy._today(), CAP_PER_USER)

    class FlakyRollback:
        def __init__(self, real):
            self.real, self.n = real, 0

        def pipeline(self):
            self.n += 1
            if self.n == 2:  # 第二个 pipeline = 回滚
                raise ConnectionError("down")
            return self.real.pipeline()

    assert _charge("u1", None, 8, redis=FlakyRollback(r)) == "user"


def test_same_item_charged_once_per_day(r):
    assert _charge("u1", "1.2.3.4", 8, redis=r, item="gen:Q1") is None
    assert _charge("u1", "1.2.3.4", 8, redis=r, item="gen:Q1") is None
    assert _used(r, "u", "u1") == 8
    assert _charge("u1", "1.2.3.4", 3, redis=r, item="tr:Q1:de") is None
    assert _used(r, "u", "u1") == 11  # 别的动作照扣


def test_rejected_item_is_not_marked_paid(r):
    """超限被拒的那次不算付过:否则第二天之前再点同一件会白放行。"""
    r.set(f"lazy:u:u1:{lazy._today()}", CAP_PER_USER)
    assert _charge("u1", None, 8, redis=r, item="gen:Q9") == "user"
    assert _charge("u1", None, 8, redis=r, item="gen:Q9") == "user"
