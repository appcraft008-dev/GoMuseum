"""启动钩子从 on_event 迁到 lifespan(2026-09-30):迁完必须仍在启动时跑建库与搜索预热。"""

from unittest.mock import patch

from fastapi.testclient import TestClient

import app.main as main


def test_startup_runs_init_db_and_search_warmup(monkeypatch):
    from app.services import llm_usage

    monkeypatch.setattr(llm_usage, "ORIGIN_SUFFIX", "")
    calls = []
    with (
        patch.object(main, "init_db", lambda: calls.append("init_db")),
        patch(
            "app.services.search.inprocess.warm_search_index",
            lambda: calls.append("warm"),
        ),
        patch(
            "app.services.recognition.vector_index.warm_vector_index",
            lambda: calls.append("warm_vec"),
        ),
        patch(
            "app.services.storage.get_object_storage",
            lambda: calls.append("storage"),
        ),
        patch(
            "app.services.recognition.embedder.warm_embedder",
            lambda: calls.append("embedder"),
        ),
    ):
        with TestClient(main.app):
            pass
    assert calls == ["init_db", "warm", "warm_vec", "storage", "embedder"]
    # 在线服务进程的 AI 用量记成 xxx@app,与离线脚本分开(P3-14③)
    assert llm_usage.ORIGIN_SUFFIX == "@app"
