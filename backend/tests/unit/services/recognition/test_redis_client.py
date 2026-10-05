"""识别缓存的 Redis 客户端(2026-10-05 修):此前 `_get_redis()` 导入不存在的
`get_cache_service`,ImportError 被吞 → 恒 None → prod 缓存从未命中(0 条 engine=cache)。"""

import pytest

from app.services.recognition import service

pytestmark = pytest.mark.real_recog_redis  # 不吃 conftest 的「_get_redis→None」桩


class _FakeClient:
    made = 0
    ping_ok = True

    def __init__(self, **kw):
        type(self).made += 1
        self.kw = kw

    def ping(self):
        if not type(self).ping_ok:
            raise ConnectionError("down")
        return True


@pytest.fixture(autouse=True)
def _fresh(monkeypatch):
    _FakeClient.made = 0
    _FakeClient.ping_ok = True
    monkeypatch.setattr(service.redis_lib, "Redis", _FakeClient)
    monkeypatch.setattr(service, "_redis_state", {"client": None, "failed_at": None})


def test_get_redis_returns_client_and_memoizes():
    c1 = service._get_redis()
    c2 = service._get_redis()
    assert isinstance(c1, _FakeClient) and c1 is c2
    assert _FakeClient.made == 1
    # 超时要短:Redis 抖动不能给每次识别加 5 秒
    assert c1.kw["socket_timeout"] <= 1


def test_get_redis_down_returns_none_and_backs_off(monkeypatch):
    _FakeClient.ping_ok = False
    now = [1000.0]
    monkeypatch.setattr(service.time, "monotonic", lambda: now[0])
    assert service._get_redis() is None
    assert service._get_redis() is None  # 冷却期内不重连
    assert _FakeClient.made == 1
    _FakeClient.ping_ok = True
    now[0] += 61
    assert isinstance(service._get_redis(), _FakeClient)  # 冷却后恢复


def test_cache_key_changes_with_engine(monkeypatch):
    monkeypatch.setattr(service.settings, "RECOG_MODEL", "dinov3-vits16")
    k1 = service._cache_key(None, "sha", "en")
    monkeypatch.setattr(service.settings, "RECOG_MODEL", "dinov4-x")
    k2 = service._cache_key(None, "sha", "en")
    assert k1 != k2  # 换引擎不能吃旧引擎的缓存结果
    assert k1.startswith("recog3:global:")
