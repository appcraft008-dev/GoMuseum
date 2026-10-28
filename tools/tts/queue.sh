#!/bin/bash
# 多批串行排队 + 随时暂停/续跑。批次本身仍由 start_run.sh 起(唯一入口)。
#
# 存在的理由:2026-10-26 手搓的串联脚本只看「run_chunked 进程还在不在」,
# 让出资源时一 kill,它当成「这批跑完了」直接起了下一批(意语提前开跑);
# 后来又加了一个「等串联结束再起」的收尾进程,暂停时漏杀它就会抢跑。
# 这里只认 run_chunked 写的 ALLDONE(alldone_since_start.sh):被杀的批次
# 没有 ALLDONE → 队列停下,不往下走;续跑时已完成的批次直接跳过。
#
# 用法: queue.sh start|pause|status [队列文件]   不给 = ~/tts-lab/queue*.txt 全部
# 队列文件每行「<jobs.json> <输出目录>」,相对 ~/tts-lab,# 开头为注释。
# 文件名含 modal 的队列(如 queue_modal.txt)生成放 Modal(TTS_GPU=modal),与 Mac 队列
# 并行;月度硬上限靠 Modal 后台 usage limit(本地估不准:app list 不含早先的 app),
# 本地 MAX_USD 取 MODAL_MAX_USD(默认 28)只兜单次。pause/start 一次管全部队列,两边不会一停一跑。
# ⚠️ 在受限沙箱里起 Modal 队列会连不上 input-plane(TimeoutError),要在沙箱外起。
set -uo pipefail

HERE=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
LAB=${TTS_LAB:-$HOME/tts-lab}
QS=("${@:2}"); [ ${#QS[@]} -gt 0 ] || QS=("$LAB"/queue*.txt)

alive() { pgrep -f "queue.sh run" >/dev/null || pgrep -f run_chunked.sh >/dev/null || pgrep -f tools/tts/run_batch.py >/dev/null; }
# 撞费用闸也会走到 ALLDONE(run_batch 正常 break),但没跑完 —— 不能算完成
batch_done() { local L="$LAB/run_$(basename "${1%.json}").log"
  "$HERE/alldone_since_start.sh" "$L" 2>/dev/null && ! awk '/^=== 起跑 /{c=0} /费用闸/{c=1} END{exit !c}' "$L"; }

case ${1:-} in
run)  # 内部:由 start 用 nohup 拉起,一个队列文件一个进程
  Q=$2; cd "$LAB" || exit 1
  # 月度硬上限靠 Modal 后台 usage limit(服务端精确);MAX_USD 只是单次运行的本地兜底
  [[ $(basename "$Q") == *modal* ]] && export TTS_GPU=modal MAX_USD=${MODAL_MAX_USD:-28}
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
  for Q in "${QS[@]}"; do
    [ -f "$Q" ] || { echo "❌ 队列文件不存在: $Q" >&2; exit 1; }
    nohup "$HERE/queue.sh" run "$Q" >> "${Q%.txt}.log" 2>&1 &
  done
  sleep 75   # 模型加载 + start_run 自己的判活
  rc=0
  for Q in "${QS[@]}"; do
    if pgrep -f "queue.sh run $Q" >/dev/null; then echo "✅ 在跑  $(basename "$Q")  日志: ${Q%.txt}.log"
    else echo "⚠️ 已退出 $(basename "$Q")(全部完成或启动失败):"; tail -3 "${Q%.txt}.log"; rc=1; fi
  done
  echo "run_batch 进程数: $(pgrep -f tools/tts/run_batch.py | wc -l | tr -d ' ')"
  exit $rc ;;
pause)
  # 先杀队列,再杀批次:反过来的话队列会看见批次没了而去起下一批
  pkill -f "queue.sh run"; pkill -f run_chunked.sh; pkill -f tools/tts/run_batch.py
  for _ in $(seq 1 10); do alive || { echo "⏸ 已全部停止"; exit 0; }; sleep 1; done
  echo "❌ 仍有进程存活:" >&2; pgrep -fl "queue.sh run|run_chunked.sh|run_batch.py" >&2; exit 1 ;;
status)
  cd "$LAB" || exit 1
  for Q in "${QS[@]}"; do echo "== $(basename "$Q")"; while read -r J O; do
    [[ -z "$J" || "$J" == \#* ]] && continue
    s=$(batch_done "$J" && echo 完成 || echo 未完成)
    echo "$s $J → $O  $(python3 -c "import json,os,sys;t=len(json.load(open(sys.argv[1])));f=sys.argv[2]+'/_state.json';s=json.load(open(f)) if os.path.exists(f) else {};print(f'{len(s)}/{t} 合格{sum(1 for v in s.values() if v.get(\"ok\"))}')" "$J" "$O")"
  done < "$Q"; done
  alive && echo "进程:运行中" || echo "进程:无" ;;
*) echo "用法: $0 start|pause|status [队列文件]" >&2; exit 1 ;;
esac
