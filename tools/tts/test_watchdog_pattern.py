"""存活检测模式的正反样本测试。

为什么需要:2026-09-04 看门狗的 `pgrep -f run_batch.py` 会匹配到**看门狗自己**
——它的命令行里就写着这个进程名。于是「进程消失」这个报警从装上去那天起
就永远不会触发,而它坏掉的方式恰好是"永远安静",和"一切正常"无法区分。

反向样本(命令行只是提到进程名)不能省:只测"能认出真进程"的话,
把模式放宽成 `run_batch` 也能过测,而那正是原来的 bug。
"""

import re
import subprocess
import sys
import time
from pathlib import Path

WATCH = Path(__file__).parent / "watch_run.sh"


def liveness_patterns() -> list[str]:
    """从脚本里取真正在用的模式,而不是在测试里抄一份(抄的会和实现漂移)。"""
    pats = re.findall(r'pgrep -f "([^"]+)"', WATCH.read_text())
    assert pats, "watch_run.sh 里没找到 pgrep -f \"...\" 形式的存活检测"
    return pats


def matches(pattern: str, pid: int) -> bool:
    out = subprocess.run(
        ["pgrep", "-f", pattern], capture_output=True, text=True
    ).stdout.split()
    return str(pid) in out


def test_pattern_finds_the_real_worker(tmp_path):
    """正样本:真的用 python 跑一个叫 run_batch.py 的进程,必须被认出来。"""
    script = tmp_path / "run_batch.py"
    script.write_text("import time; time.sleep(30)\n")
    proc = subprocess.Popen([sys.executable, str(script)])
    try:
        time.sleep(1.5)
        pats = liveness_patterns()
        assert any(
            matches(p, proc.pid) for p in pats
        ), f"真跑批进程没被任何模式认出:{pats}"
    finally:
        proc.kill()
        proc.wait()


def test_pattern_ignores_processes_that_merely_mention_it():
    """反样本:命令行里只是**提到** run_batch.py 的进程(看门狗自己就是这样),
    不能被当成跑批进程 —— 否则"进程消失"永远不触发。"""
    # ⚠️ 必须用 while 循环:`bash -c "sleep 30 # 注释"` 会被 bash 的 exec 优化
    # 直接替换成 `sleep 30`,命令行里那句提及消失 —— 反样本就成了空的,
    # 测试会"通过"而什么也没验到(第一版就是这么假通过的)。
    proc = subprocess.Popen(
        ["bash", "-c", "while :; do sleep 1; done  # pgrep -f run_batch.py run_chunked.sh"]
    )
    try:
        time.sleep(1.5)
        wrong = [p for p in liveness_patterns() if matches(p, proc.pid)]
        assert not wrong, f"模式误伤了只是提到进程名的命令行:{wrong}"
    finally:
        proc.kill()
        proc.wait()
