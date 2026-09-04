#!/bin/bash
# TTS 跑批的事件流:每行 stdout 是一个事件(供 Monitor 工具消费)。
#
# 存在的理由:同一个坑踩了三次 —— 手写的过滤器漏掉失败签名,日志安静被读成
# "在跑"。**沉默既是「正常」也是「全死了」,在通知流里长得一模一样。**
# 所以覆盖面必须进仓库、由 test_watch_run.py 用已知失败样本守着,而不是
# 每次现写、每次靠记性。
#
# 用法: tools/tts/watch_run.sh <日志> <输出目录> <总条数>
# 事件: 每 15 条一次带指标的进度 / 未过闸 / 擦边 / 块头 / 崩溃 / 卡死 / 完成
set -uo pipefail

LOG=$1; DIR=$2; TOTAL=$3
STALL=${STALL:-1800}          # 最新文件多久没更新算卡死

# —— 存活/卡死/完成:轮询,不依赖日志有没有输出 ——
(
  while true; do
    n=$(ls "$DIR"/*.mp3 2>/dev/null | wc -l | tr -d ' ')
    if grep -q ALLDONE "$LOG" 2>/dev/null; then echo "✅ 生成完成 ${n}/${TOTAL}"; break; fi
    # ⚠️ 模式必须能排除**看门狗自己** —— 本脚本的命令行里就写着这些进程名,
    # 用 `pgrep -f run_batch.py` 会匹配到自身,「进程消失」永远不触发
    # (2026-09-04 实测:这个检测装上去就是坏的,而坏法恰好是"永远安静")。
    # 带上 bin/python / bash 前缀,且用 [^ ]* 而不是 .* —— .* 会跨过空格,
    # 把「命令行里顺带提到这个名字」的进程也算进来(测试实测抓到过)。
    # 前提:仓库与 lab 路径不含空格。
    if ! pgrep -f "bin/python [^ ]*run_batch\.py" >/dev/null \
       && ! pgrep -f "bash [^ ]*run_chunked\.sh" >/dev/null; then
      echo "🔴 生成进程消失,停在 ${n}/${TOTAL} —— $(tail -3 "$LOG" 2>/dev/null | tr '\n' ' ')"; break
    fi
    newest=$(ls -t "$DIR"/*.mp3 2>/dev/null | head -1)
    if [ -n "$newest" ]; then
      age=$(( $(date +%s) - $(stat -f %m "$newest" 2>/dev/null || stat -c %Y "$newest") ))
      [ "$age" -gt "$STALL" ] && { echo "⚠️ 最新文件已 ${age}s 无更新,疑似卡死,停在 ${n}/${TOTAL}"; break; }
    fi
    sleep 180
  done
) &

# —— 质量事件:日志流 ——
# 过滤逻辑在 watch_filter.sh(单独成文件才能被 test_watch_run.py 测)。
tail -f "$LOG" 2>&1 | "$(dirname "${BASH_SOURCE[0]}")/watch_filter.sh"
