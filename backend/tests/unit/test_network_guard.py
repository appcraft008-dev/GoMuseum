"""conftest 的外网禁连闸自检。

这道闸本身没有别的测试会踩到它(踩到的那些用例把异常吞了,照样绿),
所以它坏掉是静默的 —— 那就等于 2026-09-20 的 #606 重演:
backend-tests 跑到 99% 被 `timeout-minutes: 10` cancel。
"""

import socket

import pytest

# ⚠️ 必须 `import conftest`,不能 `from tests.conftest import`:tests/ 没有
# __init__.py,后者会经 namespace package 再导入一次,拿到**另一个**类对象,
# isinstance/raises 全对不上。
from conftest import NetworkUseInTest


def test_outbound_connection_is_refused():
    with pytest.raises(NetworkUseInTest):
        socket.create_connection(("185.15.58.224", 443), timeout=1)


def test_localhost_still_reachable():
    """CI 的 postgres/redis 是本机服务容器,闸不能把它们一起关了。

    连一个几乎必然没人监听的本地端口:放行的证据是它报"拒绝连接"
    (说明真走到了系统调用),而不是报本闸的异常。
    """
    with pytest.raises(OSError) as e:
        socket.create_connection(("127.0.0.1", 9), timeout=1)
    assert not isinstance(e.value, NetworkUseInTest)
