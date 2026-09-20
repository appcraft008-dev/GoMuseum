"""Pytest 全局配置：测试环境关闭速率限制 + 禁止测试访问外网"""

import os
import socket

import pytest

os.environ.setdefault("RATE_LIMIT_ENABLED", "0")

_real_connect = socket.socket.connect
# CI 的 DATABASE_URL/REDIS_URL 都是本机服务容器，这两个必须放行。
_LOCAL = {"127.0.0.1", "::1", "localhost", "0.0.0.0"}


class NetworkUseInTest(RuntimeError):
    """测试摸到了外网。注入那个 fetch_*，别让用例去问 Wikidata。"""


@pytest.fixture(autouse=True)
def _no_outbound_network(monkeypatch):
    """测试期间禁止连外网。

    起因：`backfill_display_names` 的 `fetch_artist_facts_i18n` 参数没被注入时
    会回落到真的 Wikidata SPARQL 查询，而 `test_backfill_names.py` 只注入了
    `fetch_labels`/`fetch_creators`。文件开头写着"离线可测"，实际每建一个
    Artist 行就打一次 query.wikidata.org —— 单个用例 60 秒，整份后端用例
    在 2 分 40 秒和 10 分钟之间随 Wikidata 的心情漂移，2026-09-20 直接把
    backend-tests 的 `timeout-minutes: 10` 撑爆（#606，跑到 99% 被 cancel）。

    这里堵在**一个**地方而不是逐个用例补注入：漏注入的下一个用例照样会静默触网。
    触网现在是秒级的响亮失败，而不是十分钟后的一次 cancel。
    """

    def guard(self, address, *a, **kw):
        # 非 tuple = AF_UNIX 的路径,本机通信,放行。
        if isinstance(address, tuple) and address[0] not in _LOCAL:
            raise NetworkUseInTest(f"测试连了外网 {address}；把对应的 fetch_* 注入掉")
        return _real_connect(self, address, *a, **kw)

    monkeypatch.setattr(socket.socket, "connect", guard)


def account_tables():
    """删号路径会碰到的全部表。

    这些 fixture 用 SQLite 只建"本用例涉及的表"(个别模型的 server_default NOW()
    不兼容 SQLite，不能 create_all 全量)。但删号是横跨多张表的一个动作，
    各 fixture 手抄一份清单的话，**下次给删号加一张表就会在别处静默炸掉** ——
    #585 就是这么炸的：加了 feedbacks 后 `test_password_reset` 的 fixture 缺这张表，
    而本地只跑改动到的那两个文件根本看不见。

    所以清单在这里只有一份，凡是会走到 `delete_user_account` 的 fixture 都用它。
    给删号新加表时改这里，不必去找有哪些 fixture 抄过。
    """
    from app.models.auth_token import AuthToken
    from app.models.feedback import Feedback
    from app.models.purchase import Entitlement, Purchase
    from app.models.recognition_event import RecognitionEvent
    from app.models.user import User
    from app.models.user_benefits import UserBenefits

    return [
        User.__table__,
        UserBenefits.__table__,
        AuthToken.__table__,
        Purchase.__table__,
        Entitlement.__table__,
        RecognitionEvent.__table__,
        Feedback.__table__,
    ]
