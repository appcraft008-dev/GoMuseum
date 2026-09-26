"""音频损失闸(契约纪律 37)挂在 guarded_sessionmaker 上 —— 直接调 sessionmaker 就绕过它。

补语种线程池曾自己 `sessionmaker(bind=...)`,那条路径的音频损失闸是看不见的。
这条测试让「新写一个自建会话的脚本」在 CI 里直接红,而不是悄悄绕过。
"""

import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parents[2]
ALLOWED = {ROOT / "app" / "core" / "database.py"}  # guarded_sessionmaker 自身


def test_no_bare_sessionmaker_in_app_or_scripts():
    bad = []
    for d in ("app", "scripts"):
        for f in (ROOT / d).rglob("*.py"):
            if f in ALLOWED:
                continue
            for i, line in enumerate(f.read_text(encoding="utf-8").splitlines(), 1):
                code = line.split("#", 1)[0]
                if re.search(r"(?<![\w.])sessionmaker\(", code):
                    bad.append(f"{f.relative_to(ROOT)}:{i}: {line.strip()}")
    assert (
        not bad
    ), "用 app.core.database.guarded_sessionmaker,别直接 sessionmaker:\n" + "\n".join(
        bad
    )
