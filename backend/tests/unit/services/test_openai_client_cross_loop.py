"""共享 OpenAI client 跨 asyncio.run 复用时不该每次先失败重试一次。

调用方(complete / 识别兜底 / 看图)每次调用都 asyncio.run 换新 loop;keep-alive 池里
挂在上一个已关 loop 上的连接被复用 → 连接错误 → SDK 等 ~0.5s 重试(prod 297 次调用 275 次重试)。
"""

import asyncio
import json
import logging
import socketserver
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from app.services import content_generation_service as cgs

_BODY = json.dumps(
    {
        "id": "x",
        "object": "chat.completion",
        "created": 0,
        "model": "m",
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": "ok"},
                "finish_reason": "stop",
            }
        ],
        "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
    }
).encode()


class _Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"  # keep-alive,和 api.openai.com 一样

    def do_POST(self):
        self.rfile.read(int(self.headers["Content-Length"]))
        self.server.hits += 1
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(_BODY)))
        self.end_headers()
        self.wfile.write(_BODY)

    def log_message(self, *a):
        pass


class _Server(ThreadingHTTPServer):
    def server_bind(self):  # 跳过 HTTPServer 的 getfqdn 反查(本机可卡 35s)
        socketserver.TCPServer.server_bind(self)


def test_reused_client_across_asyncio_run_does_not_retry(monkeypatch, caplog):
    srv = _Server(("127.0.0.1", 0), _Handler)
    srv.hits = 0
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    monkeypatch.setenv(
        "OPENAI_BASE_URL", f"http://127.0.0.1:{srv.server_address[1]}/v1"
    )
    monkeypatch.setattr(cgs.settings, "OPENAI_API_KEY", "test-key")
    monkeypatch.setattr(cgs._openai_tl, "client", None, raising=False)
    try:
        client = cgs._get_openai_client()

        async def call():
            await client.chat.completions.create(
                model="m", messages=[{"role": "user", "content": "hi"}]
            )

        with caplog.at_level(logging.INFO, logger="openai"):
            for _ in range(3):
                asyncio.run(call())
    finally:
        srv.shutdown()
    assert not [r for r in caplog.records if "Retrying" in r.getMessage()]
    assert srv.hits == 3
