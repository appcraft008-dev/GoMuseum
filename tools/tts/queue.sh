#!/bin/bash
# 多批串行排队 + 随时暂停/续跑。批次本身仍由 start_run.sh 起(唯一入口)。
#
# 存在的理由:2026-10-26 手搓的串联脚本只看「run_chunked 进程还在不在」,
# 让出资源时一 kill,它当成「这批跑完了」直接起了下一批(意语提前开跑);
# 后来又加了一个「等串联结束再起」的收尾进程,暂停时漏杀它就会抢跑。
# 这里只认 run_chunked 写的 ALLDONE(alldone_since_start.sh):被杀的批次
# 没有 ALLDONE → 队列停下,不往下走;续跑时已完成的批次直接跳过。
#
# 用法: queue.sh start|pause|status [队列文件=~/tts-lab/queue.txt]
# 队列文件每行「<jobs.json> <输出目录>」,相对 ~/tts-lab,# 开头为注释。
set -uo pipefail

HERE=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
LAB=${TTS_LAB:-$HOME/tts-lab}
Q=${2:-$LAB/queue.txt}
QLOG=$LAB/queue.log

alive() { pgrep -f "queue.sh run" >/dev/null || pgrep -f run_chunked.sh >/dev/null || pgrep -f tools/tts/run_batch.py >/dev/null; }
batch_done() { "$HERE/alldone_since_start.sh" "$LAB/run_$(basename "${1%.json}").log"; }

case ${1:-} in
run)  # 内部:由 start 用 nohup 拉起
  cd "$LAB" || exit 1
  while read -r J O <&3; do
    [[ -z "$J" || "$J" == \#* ]] && continue
    if batch_done "$J"; then echo "$(date '+%F %T') 跳过(已完成) $J"; continue; fi
    echo "$(date '+%F %T') 起 $J"
    "$HERE/start_run.sh" "$J" "$O" 10 || { echo "❌ $J 启动失败,队列停"; exit 1; }
    while pgrep -f "run_chunked.sh .*$(basename "$J")" >/dev/null; do sleep 60; done
    batch_done "$J" || { echo "$(date '+%F %T') ⏸ $J 没跑完就停了(暂停或崩溃),队列停"; exit 1; }
    echo "$(date '+%F %T') 完 $J"
  done 3< "$Q"
  echo "$(date '+%F %T') 队列全部完成" ;;
start)
  alive && { echo "❌ 已有批次在跑,先 pause" >&2; exit 1; }
  [ -f "$Q" ] || { echo "❌ 队列文件不存在: $Q" >&2; exit 1; }
  nohup "$HERE/queue.sh" run "$Q" >> "$QLOG" 2>&1 &
  for _ in $(seq 1 15); do
    sleep 5
    pgrep -f tools/tts/run_batch.py >/dev/null && { echo "✅ 已续跑  日志: $QLOG"; exit 0; }
    pgrep -f "queue.sh run" >/dev/null || break
  done
  tail -5 "$QLOG"
  pgrep -f "queue.sh run" >/dev/null || { echo "队列进程已退出(全部完成或启动失败),见上" >&2; exit 1; }
  echo "❌ 75 秒内没看到 run_batch.py" >&2; exit 1 ;;
pause)
  # 先杀队列,再杀批次:反过来的话队列会看见批次没了而去起下一批
  pkill -f "queue.sh run"; pkill -f run_chunked.sh; pkill -f tools/tts/run_batch.py
  for _ in $(seq 1 10); do alive || { echo "⏸ 已全部停止"; exit 0; }; sleep 1; done
  echo "❌ 仍有进程存活:" >&2; pgrep -fl "queue.sh run|run_chunked.sh|run_batch.py" >&2; exit 1 ;;
status)
  cd "$LAB" || exit 1
  while read -r J O; do
    [[ -z "$J" || "$J" == \#* ]] && continue
    s=$(batch_done "$J" && echo 完成 || echo 未完成)
    echo "$s $J → $O  $(python3 -c "import json,os,sys;t=len(json.load(open(sys.argv[1])));f=sys.argv[2]+'/_state.json';s=json.load(open(f)) if os.path.exists(f) else {};print(f'{len(s)}/{t} 合格{sum(1 for v in s.values() if v.get(\"ok\"))}')" "$J" "$O")"
  done < "$Q"
  alive && echo "进程:运行中" || echo "进程:无" ;;
*) echo "用法: $0 start|pause|status [队列文件]" >&2; exit 1 ;;
esac
