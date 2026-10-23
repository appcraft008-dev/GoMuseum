"""懒生成并发数是配置项(spec §10):进程启动时读 .env,默认仍为 2(阶段 1 改 4)。"""

import os
import subprocess
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[3]


def _capacity(extra_env):
    env = {k: v for k, v in os.environ.items() if not k.startswith("LAZY_")}
    code = (
        "from app.services.enrichment import lazy\n"
        "n = lambda s: sum(s.acquire(blocking=False) for _ in range(10))\n"
        "print(n(lazy._SEM), n(lazy._FANOUT_SEM))"
    )
    out = subprocess.run(
        [sys.executable, "-c", code],
        env={**env, **extra_env},
        cwd=BACKEND,
        capture_output=True,
        text=True,
        check=True,
    )
    return out.stdout.split()


def test_default_is_two():
    assert _capacity({}) == ["2", "2"]


def test_read_from_env():
    assert _capacity({"LAZY_CONCURRENCY": "4", "LAZY_FANOUT_CONCURRENCY": "3"}) == [
        "4",
        "3",
    ]
