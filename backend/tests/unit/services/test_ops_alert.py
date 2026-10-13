"""运维告警:没配收件人要喊出来;请求路径的告警同 key 节流、不阻塞、不抛。"""

import pytest

from app.services import mailer, ops_alert


@pytest.fixture(autouse=True)
def _sync(monkeypatch):
    ops_alert._last.clear()

    class _Now:  # 线程同步执行,测试里好断言
        def __init__(self, target, **_):
            self.target = target

        def start(self):
            self.target()

    monkeypatch.setattr(ops_alert.threading, "Thread", _Now)


def test_send_requires_recipient(monkeypatch):
    monkeypatch.setattr(ops_alert.settings, "OPS_ALERT_EMAIL", None)
    with pytest.raises(mailer.MailNotConfigured):
        ops_alert.send("s", "b")


def test_throttled_sends_once_per_key(monkeypatch):
    sent = []
    monkeypatch.setattr(ops_alert.settings, "OPS_ALERT_EMAIL", "ops@x")
    monkeypatch.setattr(mailer, "send", lambda to, s, b: sent.append((to, s)))
    ops_alert.alert_throttled("k", "s1", "b")
    ops_alert.alert_throttled("k", "s2", "b")
    ops_alert.alert_throttled("other", "s3", "b")
    assert sent == [("ops@x", "s1"), ("ops@x", "s3")]


def test_throttled_swallows_send_failure(monkeypatch):
    monkeypatch.setattr(ops_alert.settings, "OPS_ALERT_EMAIL", None)
    ops_alert.alert_throttled("k", "s", "b")  # 不抛
