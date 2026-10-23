"""大模型调用显式超时(spec §3.4 / B12):SDK 默认 600 秒外加 2 次重试,
一次挂住的调用能占住生成线程半小时。"""

import socketserver
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import openai
import pytest

from app.services import content_generation_service as cgs
from app.services import openai_models


class _Hang(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def do_POST(self):
        self.server.hits += 1
        time.sleep(5)  # 远长于测试里的超时:模拟挂住的上游
        # 不关连接的话 keep-alive 循环会卡在读下一个请求上:回归时测试挂死而不是失败
        self.close_connection = True

    def log_message(self, *a):
        pass


class _Server(ThreadingHTTPServer):
    def server_bind(self):  # 跳过 getfqdn 反查(本机可卡 35s)
        socketserver.TCPServer.server_bind(self)


@pytest.fixture()
def hanging(monkeypatch):
    srv = _Server(("127.0.0.1", 0), _Hang)
    srv.hits = 0
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    monkeypatch.setenv(
        "OPENAI_BASE_URL", f"http://127.0.0.1:{srv.server_address[1]}/v1"
    )
    monkeypatch.setattr(cgs.settings, "OPENAI_API_KEY", "test-key")
    monkeypatch.setattr(cgs._openai_tl, "client", None, raising=False)
    monkeypatch.setattr(openai_models.settings, "LLM_CHANNEL_MODELS", {})
    yield srv
    srv.shutdown()
    srv.server_close()  # filterwarnings=error:没关的 socket 会变成 ResourceWarning 报错


def _ask(**kw):
    return openai_models.chat("gpt-4o-mini", [{"role": "user", "content": "hi"}], **kw)


def _wait_hits(srv, n):
    for _ in range(40):  # 第 3 次请求要等服务端线程解析完才计数,CI 忙时会晚一点
        if srv.hits >= n:
            return
        time.sleep(0.05)


def test_hanging_call_fails_after_llm_timeout(hanging, monkeypatch):
    monkeypatch.setattr(openai_models.settings, "LLM_TIMEOUT_S", 0.3)
    t = time.monotonic()
    with pytest.raises(openai.APITimeoutError):
        _ask(channel="generate")
    assert time.monotonic() - t < 8  # 3 次 × 0.3 秒 + SDK 退避
    _wait_hits(hanging, 3)
    assert hanging.hits == 3  # 1 次 + SDK 默认重试 2 次


def test_explicit_timeout_still_wins(hanging, monkeypatch):
    """识别兜底自己传 30 秒(recognition/vision.py),默认值不能盖掉它。"""
    monkeypatch.setattr(openai_models.settings, "LLM_TIMEOUT_S", 60)
    t = time.monotonic()
    with pytest.raises(openai.APITimeoutError):
        _ask(channel="recognition", timeout=0.3)
    assert time.monotonic() - t < 8


def test_claude_path_gets_default_timeout_with_short_connect(monkeypatch):
    """prod 的 generate/gate/qa/label 走 Claude;默认超时要传到 SDK,连接超时保持 5 秒(R10)。"""
    seen = {}

    class _Messages:
        def create(self, **kw):
            seen.update(kw)
            usage = type("U", (), {"input_tokens": 1, "output_tokens": 1})()
            return type("R", (), {"content": [], "usage": usage})()

    client = type("C", (), {"messages": _Messages()})()
    monkeypatch.setattr(openai_models, "_anthropic_client", lambda: client)
    monkeypatch.setattr(
        openai_models.settings, "LLM_CHANNEL_MODELS", {"generate": "claude-haiku-5-5"}
    )
    monkeypatch.setattr(openai_models.settings, "LLM_TIMEOUT_S", 90)
    openai_models.chat(
        "gpt-4o-mini", [{"role": "user", "content": "hi"}], channel="generate"
    )
    assert (seen["timeout"].read, seen["timeout"].connect) == (90, 5)
