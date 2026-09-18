"""按 IP 限流依赖 request.client.host 是**真实访客 IP**，这组测试钉住这件事。

背景见 `app/main.py` 里 TRUSTED_PROXY_HOSTS 的注释：没有 ProxyHeadersMiddleware 时
容器只看得到 docker 网桥网关，全站共享一个限流桶。

⚠️ 这类缺陷单测本来抓不到（TestClient 进程内直连、不经 nginx，行为"正常"），
所以这里直接构造 ASGI scope 复现那条链路 —— 中间件的契约就是改写 scope["client"]，
测它比绕一层 HTTP 更准。
"""

import asyncio

from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware

from app.main import TRUSTED_PROXY_HOSTS
from app.main import app as real_app

# 容器实际看到的对端（prod 实测），和一个绝不该被信任的公网地址。
BRIDGE_GATEWAY = "172.22.0.1"
UNTRUSTED_PEER = "203.0.113.9"


def resolved_client(peer: str, xff: str | None, trusted=None) -> str:
    """让中间件处理一个请求，返回它最终认定的客户端 IP。"""
    seen: dict[str, str] = {}

    async def inner_app(scope, receive, send):
        seen["host"] = scope["client"][0]

    mw = ProxyHeadersMiddleware(
        inner_app,
        trusted_hosts=TRUSTED_PROXY_HOSTS if trusted is None else trusted,
    )
    scope = {
        "type": "http",
        "scheme": "http",
        "method": "GET",
        "path": "/",
        "headers": [(b"x-forwarded-for", xff.encode())] if xff else [],
        "client": (peer, 40000),
    }

    async def receive():  # pragma: no cover - 中间件不读 body
        return {"type": "http.request"}

    async def send(_):  # pragma: no cover - 内层 app 不发响应
        return None

    asyncio.run(mw(scope, receive, send))
    return seen["host"]


def test_真实访客ip被采信():
    """正常链路：nginx 把访客 IP 放进 XFF，应采信它而非网桥网关。"""
    assert resolved_client(BRIDGE_GATEWAY, "198.51.100.7") == "198.51.100.7"


def test_伪造的xff前缀不被采信():
    """🔴 本组最重要的一条。

    nginx 用 `$proxy_add_x_forwarded_for`（追加语义）：访客自带的 XFF 会被保留，
    nginx 把真实 remote_addr 追加在**右边**。所以攻击者发 `X-Forwarded-For: 1.2.3.4`
    时，后端收到的是 `1.2.3.4, <真实IP>`。

    必须取右边那个。取左边（uvicorn 在 trusted_hosts="*" 时的行为）等于让攻击者
    每个请求换一个假 IP，限流完全失效 —— 比修之前的「全站一个桶」更糟。
    """
    host = resolved_client(BRIDGE_GATEWAY, "1.2.3.4, 198.51.100.7")
    assert host == "198.51.100.7", "取了伪造的最左端 → 限流可被绕过"


def test_不可信对端的转发头一律忽略():
    """万一容器被直接暴露，来路不明的对端说什么都不算。"""
    assert resolved_client(UNTRUSTED_PEER, "1.2.3.4") == UNTRUSTED_PEER


def test_没有转发头时保持对端地址():
    assert resolved_client(BRIDGE_GATEWAY, None) == BRIDGE_GATEWAY


def test_星号会被取最左端因此禁止使用():
    """负对照：证明 `"*"` 确实危险，不是我们多虑。

    这条同时锁住「后人图省事把 TRUSTED_PROXY_HOSTS 改成 '*'」——
    真改了，上面那条伪造测试会红，而这条解释为什么。
    """
    host = resolved_client(BRIDGE_GATEWAY, "1.2.3.4, 198.51.100.7", trusted="*")
    assert host == "1.2.3.4"  # 取了伪造值 —— 所以生产不能用 "*"
    assert "*" not in TRUSTED_PROXY_HOSTS


def test_生产app真的装了这个中间件():
    """上面几条测的是配置值；这条确保它真被挂到生产 app 上。"""
    assert any(
        m.cls is ProxyHeadersMiddleware for m in real_app.user_middleware
    ), "app/main.py 没装 ProxyHeadersMiddleware，限流会退回全站一个桶"
