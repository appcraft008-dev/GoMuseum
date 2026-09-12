"""开跑前预检:每条任务的正文能不能真取到 + 估算成品音频时长。

为什么必须跑:一批十几小时,**取不到正文的条目要到跑到它那一条才暴露**,
而那时可能已经过去几小时。契约「音频批量生产与灌入」⑪ 要求排队前先体检,
这是它的执行工具。取不到正文的常见原因:段落 needs_review(未发布)、
artist_bio 漏了 via_qid、队列与 prod 内容不同步。

用法: preflight.py <jobs.json>
退出码 0 = 全部可取;1 = 有取不到的(名单打在上面,修完再开跑)。
"""

import collections
import json
import sys

from fetch_text import fetch_text

# 各语言语速基准(字/秒),与 run_batch.RATE 同源(tts-1 实测)。
# 这里只用来估工时,不参与生成,故独立一份不引 run_batch(它要 voxcpm 重依赖)。
RATE = {
    "zh": 4.64,
    "en": 15.84,
    "fr": 15.61,
    "de": 15.67,
    "es": 15.87,
    "it": 15.78,
    "pl": 14.86,
    "ja": 5.47,
    "ko": 7.31,
    "zh-hant": 4.71,
}


def main():
    jobs = json.load(open(sys.argv[1]))
    miss, chars = [], collections.defaultdict(list)
    for n, j in enumerate(jobs, 1):
        t = fetch_text(j, use_cache=True)  # 同一件的多段共用一次请求
        if t:
            chars[j["language"]].append(len(t))
        else:
            miss.append((j["qid"], j["language"], j["section"]))
        if n % 100 == 0:
            print(f"  {n}/{len(jobs)}", flush=True)

    print(f"\n任务 {len(jobs)}  取不到正文 {len(miss)}")
    for m in miss[:20]:
        print("  ❌", m)
    if len(miss) > 20:
        print(f"  …… 另有 {len(miss)-20} 条")

    tot = 0.0
    print("\n语言       条数   总字数   预计音频时长")
    for lang in sorted(chars):
        c = sum(chars[lang])
        sec = c / RATE[lang]
        tot += sec
        print(f"{lang:10s} {len(chars[lang]):4d} {c:8d}   {sec/60:6.1f} 分")
    print(f"\n成品音频合计 {tot/3600:.1f} 小时")
    return 1 if miss else 0


if __name__ == "__main__":
    sys.exit(main())
