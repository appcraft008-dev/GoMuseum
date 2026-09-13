"""监视过滤器的覆盖面测试 —— 用真实日志里出现过的失败样本守着它。

为什么需要这个测试:2026-09-04 同一个坑踩了三次 —— 手写的过滤器漏掉某类失败
签名,日志安静,被读成"还在跑"。**沉默既是「一切正常」也是「进程早死了」,
在通知流里长得一模一样。**
所以覆盖面不能靠写监视器的人当时想没想到,得靠这里的样本兜住。

新增失败签名时:先往 MUST_EMIT 加一行真实日志,再去改 watch_filter.sh。
"""

import subprocess
from pathlib import Path

FILTER = Path(__file__).parent / "watch_filter.sh"

# 每一行都来自真实跑批日志。左=输入,右=期望事件前缀(None 表示只要有输出即可)。
MUST_EMIT = [
    # —— 启动类失败:这一类曾整个漏掉,导致批次从未启动却"看起来在跑" ——
    ("nohup: tools/tts/run_chunked.sh: No such file or directory", None),
    ("bash: run_chunked.sh: command not found", None),
    ("bash: ./run_chunked.sh: Permission denied", None),
    # —— 运行时崩溃 ——
    ("Traceback (most recent call last):", None),
    ("RuntimeError: MPS backend out of memory", None),
    ("Killed", None),
    ("MemoryError", None),
    # —— 质量事件 ——
    (
        "[9/10] Q19820384__en__significance.mp3 第1次 锐度=205% 一致=0.99 "
        "长度比=1.00 35s→39s(atempo 0.91) 重试 152s",
        "⚠未过闸",
    ),
    (
        "[8/10] Q28797624__en__facts.mp3 第1次 锐度=190% 一致=1.00 "
        "长度比=1.00 30s→33s(atempo 0.91) ✅ 136s",
        "⚠擦边",
    ),
    (
        "[3/10] Q28797622__ja__facts.mp3 第1次 锐度=133% 一致=0.92 "
        "长度比=1.02 23s→22s(atempo 1.04) ✅ 97s",
        "⚠擦边",
    ),
    # 锐度爆表(近似静音,分母兜底):数值很大也必须归到未过闸,不能被当成普通行
    (
        "[8/10] Q28797625__ja__qa_1.mp3 第1次 锐度=1625750372352% 一致=0.01 "
        "长度比=0.29 30s→30s(atempo 1.00) 重试 93s",
        "⚠未过闸",
    ),
    # —— 进度/收尾 ——
    ("--- 块 180-190 / 490 ---", None),
    ("无文本,跳过", None),
    ("ALLDONE", None),
]

# 正常且不擦边的条目不该刷屏(每 EVERY 条才报一次,单行输入时应当静默)
MUST_STAY_SILENT = [
    "[2/10] Q28797620__fr__analysis.mp3 第1次 锐度=103% 一致=0.99 "
    "长度比=1.01 60s→72s(atempo 0.83) ✅ 115s",
    "[voxcpm2] adjusted dtype bfloat16 -> float32 for device mps",
    "总任务 10,待做 10(已完成 0)",
]


def run(line: str) -> str:
    p = subprocess.run(
        ["bash", str(FILTER)], input=line + "\n", capture_output=True, text=True
    )
    return p.stdout.strip()


def test_failure_signatures_all_emit():
    missed = []
    for line, expect in MUST_EMIT:
        out = run(line)
        if not out:
            missed.append(f"未出行: {line[:60]}")
        elif expect and not out.startswith(expect):
            missed.append(f"分类错({expect} → {out[:20]}): {line[:50]}")
    assert not missed, "监视过滤器漏掉失败签名:\n" + "\n".join(missed)


def test_normal_lines_stay_quiet():
    noisy = [line for line in MUST_STAY_SILENT if run(line)]
    assert not noisy, "正常行不该产生事件(会淹掉真信号):\n" + "\n".join(noisy)


# ---- 「本次起跑之后才算完成」 ----
# 回归来源:2026-09-13,同一日志先跑 1 条 smoke 再起全批,存活检测读到 smoke
# 留下的 ALLDONE,当场报「生成完成」并 break —— 卡死与进程消失检测随之一起失效。

ALLDONE_SH = Path(__file__).parent / "alldone_since_start.sh"
START = "=== 起跑 2026-09-13 06:12:00 commit abc1234 jobs=/x/j.json ==="


def alldone(log_text: str, tmp_path) -> bool:
    f = tmp_path / "run.log"
    f.write_text(log_text)
    return subprocess.run(["bash", str(ALLDONE_SH), str(f)]).returncode == 0


def test_上一次跑的ALLDONE不算数(tmp_path):
    assert not alldone(f"{START}\n完成 1/1 合格\nALLDONE\n{START}\n--- 块 0-8 / 73 ---\n", tmp_path)


def test_本次跑的ALLDONE算数(tmp_path):
    assert alldone(f"{START}\nALLDONE\n{START}\n块\nALLDONE\n", tmp_path)


def test_没有起跑标记时照常识别(tmp_path):
    # 手工直接调 run_chunked.sh 的老用法,日志里没有起跑标记。
    assert alldone("--- 块 0-8 / 8 ---\nALLDONE\n", tmp_path)


def test_日志不存在算未完成(tmp_path):
    assert subprocess.run(["bash", str(ALLDONE_SH), str(tmp_path / "nope.log")],
                          capture_output=True).returncode != 0
