"""跑批进度快报:读 _state.json 出一条摘要(进度/过闸率/按语言分布/ETA)。

⚠️ **看进度只能看 `_state.json`,不能看通知流或日志滚动**。通知与日志里
只有擦边和未过闸的条目会引人注意,正常的不出现 —— 拿它当样本必然得出
"到处都在超标"的印象(2026-09-10 实测:据此写下两条错误结论,全量回归后推翻)。

用法: progress.py <输出目录> <任务总条数>
"""

import collections
import json
import os
import statistics
import sys


def main():
    out, total = sys.argv[1], int(sys.argv[2])
    sf = os.path.join(out, "_state.json")
    st = json.load(open(sf)) if os.path.exists(sf) else {}
    done = len(st)
    ok = sum(1 for v in st.values() if v.get("ok"))
    # 首次过闸:tries 只有一条且过 —— 这才是生成质量的真实水平,过闸率不是。
    # ⚠️ **重试轮跑完后这个数是高估的**:重试会覆盖该条目原来的 tries,
    # 被救回的条目事后看起来像"一次就过"(本批 554 vs 真实 551)。
    # 跑批途中看没问题;收尾统计要么用重试前存档的 _state.json,
    # 要么显式剔除重试清单里的条目。
    first = sum(
        1 for v in st.values() if v.get("ok") and len(v.get("tries") or []) == 1
    )
    retried = sum(len(v.get("tries") or []) - 1 for v in st.values())
    fail = [k for k, v in st.items() if not v.get("ok")]

    by = collections.defaultdict(lambda: [0, 0])  # lang -> [条数, 未一次过]
    sharp, consist = collections.defaultdict(list), collections.defaultdict(list)
    for k, v in st.items():
        lang = k.split("__")[1]
        by[lang][0] += 1
        if len(v.get("tries") or []) > 1:
            by[lang][1] += 1
        if v.get("sharp") is not None:
            sharp[lang].append(v["sharp"])
        if v.get("consist") is not None:
            consist[lang].append(v["consist"])

    # ETA 用产出 mp3 的 mtime 跨度算真实速率 —— 比拿"平均每条多少秒"拍脑袋准,
    # 它自动含进了重试、模型重载、机器被占用的时间。
    eta = "—"
    mp3 = [os.path.join(out, f) for f in os.listdir(out) if f.endswith(".mp3")]
    if len(mp3) >= 3:
        ts = sorted(os.path.getmtime(p) for p in mp3)
        span = ts[-1] - ts[0]
        if span > 0:
            rate = span / (len(ts) - 1)
            eta = f"{(total-done)*rate/3600:.1f} 小时(约 {rate/60:.1f} 分/条)"

    pct = done * 100 // max(total, 1)
    print(
        f"📊 进度 {done}/{total}({pct}%)  过闸 {ok}  一次过 {first}  "
        f"重试 {retried} 次  未过闸 {len(fail)}  剩余 {eta}"
    )
    worst = sorted(by.items(), key=lambda kv: -kv[1][1])[:4]
    print("   需重试最多的语言: " + "  ".join(f"{l}={n}/{c}" for l, (c, n) in worst))
    med = lambda d, l: (
        statistics.median(d[l]) if d.get(l) else float("nan")
    )  # noqa: E731
    langs = sorted(by)
    print("   锐度中位: " + " ".join(f"{l}={med(sharp,l):.0f}" for l in langs))
    print(
        "   一致中位(门槛0.90): " + " ".join(f"{l}={med(consist,l):.2f}" for l in langs)
    )
    if fail:
        print("   ❌ 未过闸: " + ", ".join(fail[:6]))


if __name__ == "__main__":
    main()
