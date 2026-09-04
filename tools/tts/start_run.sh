#!/bin/bash
# 起一批 TTS 生成,并**验证它真的在跑**才返回。
#
# 存在的理由:2026-09-04 一次重跑因为 cwd 不对、相对路径找不到脚本而从未启动
# (`nohup: run_chunked.sh: No such file or directory`),而监视器的过滤器不含
# 这类启动错误 —— 日志安静,被读成"进行中",三小时后才发现。
# **"起来了"必须是机器判定的,不能是假设。**
#
# 用法: tools/tts/start_run.sh <jobs.json> <输出目录> [每块条数=8]
# 成功: 打印日志路径,退出 0。失败: 打印日志尾,退出 1。
set -euo pipefail

HERE=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)   # 绝对路径:不依赖调用者的 cwd
JOBS=$(cd "$(dirname "$1")" && pwd)/$(basename "$1")
OUT=$2
CHUNK=${3:-8}
LOG=${LOG:-$HOME/tts-lab/run_$(basename "${JOBS%.json}").log}

[ -f "$JOBS" ] || { echo "❌ 任务文件不存在: $JOBS" >&2; exit 1; }

PY=${PY:-$HOME/tts-lab/venv/bin/python} TTS_LAB=${TTS_LAB:-$HOME/tts-lab} \
  nohup "$HERE/run_chunked.sh" "$JOBS" "$OUT" "$CHUNK" > "$LOG" 2>&1 &

# 模型加载要十几秒,给足时间再判活
for _ in $(seq 1 12); do
  sleep 5
  if pgrep -f run_batch.py >/dev/null; then
    echo "✅ 已启动并确认存活  日志: $LOG"
    exit 0
  fi
  # 进程链整个没了 = 启动失败,不必等满
  pgrep -f run_chunked.sh >/dev/null || break
done

echo "❌ 启动失败:60 秒内没看到 run_batch.py 存活" >&2
echo "--- 日志尾 ---" >&2
tail -20 "$LOG" >&2
exit 1
