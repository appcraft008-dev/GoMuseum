"""连接池在用峰值(spec §7「在用连接峰值」):每进程每分钟的最高值写进 Redis。
5 分钟一次的 pg_stat_activity 采样看不到几十秒的尖峰。"""

from datetime import datetime, timedelta, timezone

import fakeredis
import pytest

from app.core import database

NOW = datetime(2026, 10, 23, 12, 34, 56, tzinfo=timezone.utc)


@pytest.fixture(autouse=True)
def _reset(monkeypatch):
    monkeypatch.setattr(database, "_pool_peak", 0)


def test_flush_writes_minute_peak_and_resets_to_current():
    r = fakeredis.FakeRedis(decode_responses=True)
    for n in (3, 5, 2):
        database.note_checkout(n)
    assert database.flush_pool_peak(r, current=2, now=NOW) == 5
    [key] = r.keys("ops:pool_peak:202610231234:*")
    assert r.get(key) == "5" and 0 < r.ttl(key) <= 900
    # 跨分钟仍被占着的 2 个连接算进下一分钟
    assert database.flush_pool_peak(r, current=1, now=NOW + timedelta(minutes=1)) == 2


def test_flush_without_redis_or_on_error_never_raises():
    class Boom:
        def set(self, *a, **k):
            raise ConnectionError("down")

    assert database.flush_pool_peak(None, current=0, now=NOW) is None
    assert database.flush_pool_peak(Boom(), current=0, now=NOW) is None
