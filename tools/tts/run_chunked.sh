#!/bin/bash
# 分块跑,每块起一个新进程 —— 绕开 MPS 显存泄漏(实测两次:连续 26 段、122 段后 OOM)。
# 由 start_run.sh 调用。**日常入口是 start_run.sh**:直接调这里不会注入
# TTS_PIPELINE,产物没有管线版本,灌入端会拒。契约「音频批量生产与灌入」⑥。
#
# 用法: ./run_chunked.sh <jobs.json> <输出目录> [每块条数=10]
# 环境:
#   PY       生成机 venv 的 python,默认 ~/tts-lab/venv/bin/python
#   TTS_LAB  种子目录 seeds_final/ 的父目录(种子是大二进制,不入库),默认同 PY 的 lab
set -euo pipefail

JOBS=$1; OUT=$2; CHUNK=${3:-10}
# GPU 模式不分块:泄漏是 MPS 生成的事,而每起一个进程 Modal 就要冷启动一次(按秒计费)
[ "${TTS_GPU:-}" = modal ] && CHUNK=1000000
PY=${PY:-$HOME/tts-lab/venv/bin/python}
HERE=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
export TTS_LAB=${TTS_LAB:-$HOME/tts-lab}
CHUNKFILE=$(mktemp -t tts_chunk).json
trap 'rm -f "$CHUNKFILE"' EXIT

TOTAL=$("$PY" -c "import json,sys;print(len(json.load(open(sys.argv[1]))))" "$JOBS")
for ((i=0; i<TOTAL; i+=CHUNK)); do
  "$PY" -c "
import json,sys
jobs,i,n,out = sys.argv[1], int(sys.argv[2]), int(sys.argv[3]), sys.argv[4]
d=json.load(open(jobs))[i:i+n]
json.dump(d, open(out,'w'), ensure_ascii=False)
print(f'--- 块 {i}-{i+len(d)} / {len(json.load(open(jobs)))} ---')
" "$JOBS" "$i" "$CHUNK" "$CHUNKFILE"
  # 用仓库里这一份 run_batch.py(与 $HERE 同目录),别再指回本机的旧副本
  "$PY" "$HERE/run_batch.py" "$CHUNKFILE" "$OUT" 2>&1 | grep -E --line-buffered "^\[|完成|无文本|费用闸|Error"
done
echo "ALLDONE"
