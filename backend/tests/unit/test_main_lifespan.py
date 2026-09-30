"""启动钩子从 on_event 迁到 lifespan(2026-09-30):迁完必须仍在启动时跑建库与搜索预热。"""

from unittest.mock import patch

from fastapi.testclient import TestClient

import app.main as main


def test_startup_runs_init_db_and_search_warmup():
    calls = []
    with (
        patch.object(main, "init_db", lambda: calls.append("init_db")),
        patch(
            "app.services.search.inprocess.warm_search_index",
            lambda: calls.append("warm"),
        ),
    ):
        with TestClient(main.app):
            pass
    assert calls == ["init_db", "warm"]
