import pytest

from app.services.enrichment.http_client import PoliteSession


class _FakeResp:
    def __init__(self, status, headers=None, body=b"{}"):
        self.status_code = status
        self.headers = headers or {}
        self._body = body
        self.text = body.decode() if isinstance(body, bytes) else body

    def json(self):
        import json

        return json.loads(self._body)


def test_user_agent_required():
    with pytest.raises(ValueError, match="User-Agent"):
        PoliteSession(user_agent="")


def test_get_sends_user_agent_and_returns(monkeypatch):
    seen = {}

    def fake_get(url, params=None, headers=None, timeout=None):
        seen["headers"] = headers
        return _FakeResp(200, body=b'{"ok": 1}')

    s = PoliteSession(user_agent="GoMuseumBot/0.1 (contact)")
    r = s.get_json("https://x/api", params={"q": "1"}, _transport=fake_get)
    assert seen["headers"]["User-Agent"] == "GoMuseumBot/0.1 (contact)"
    assert r == {"ok": 1}


def test_backoff_on_429_then_succeeds(monkeypatch):
    calls = {"n": 0}
    sleeps = []

    def fake_get(url, params=None, headers=None, timeout=None):
        calls["n"] += 1
        if calls["n"] == 1:
            return _FakeResp(429, headers={"Retry-After": "2"})
        return _FakeResp(200, body=b'{"ok": 1}')

    s = PoliteSession(user_agent="UA", max_retries=2, sleep=sleeps.append)
    r = s.get_json("https://x", _transport=fake_get)
    assert r == {"ok": 1}
    assert calls["n"] == 2
    assert sleeps == [2.0]


def test_circuit_breaker_raises_after_repeated_failures():
    def fake_get(url, params=None, headers=None, timeout=None):
        return _FakeResp(503)

    s = PoliteSession(user_agent="UA", max_retries=2, sleep=lambda _: None)
    with pytest.raises(RuntimeError, match="耗尽重试"):
        s.get_json("https://x", _transport=fake_get)
