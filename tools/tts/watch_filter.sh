#!/bin/bash
# 跑批日志 → 事件流(读 stdin,写 stdout)。单独成文件是为了**能被测试**:
# test_watch_run.py 拿已知失败样本喂它,漏掉任何一类当场红 CI。
#
# 分类:未过闸 / 擦边(过了但贴着门槛) / 每 15 条一次的常规进度 / 其余原样透传
# ⚠️ 加失败签名时必须同步给 test_watch_run.py 加样本,否则等于没加。
set -uo pipefail
MARGIN_SHARP=${MARGIN_SHARP:-180}
MARGIN_CONSIST=${MARGIN_CONSIST:-0.93}
EVERY=${EVERY:-15}

grep -E --line-buffered "锐度=|^--- 块 |Traceback|Error|error|No such file|not found|command not found|Permission denied|Killed|OOM|MemoryError|无文本|^ALLDONE|^完成" \
  | sed -u -E "s/.*锐度=([0-9]+)% 一致=([0-9.]+).*/\1 \2 &/" \
  | awk -v ms="$MARGIN_SHARP" -v mc="$MARGIN_CONSIST" -v ev="$EVERY" '
$1 ~ /^[0-9]+$/ {
  line=$0; sub(/^[0-9.]+ [0-9.]+ /,"",line)
  if (line ~ /重试/)      { print "⚠未过闸 " line; fflush(); next }
  if ($1>ms || $2<mc)     { print "⚠擦边 " line;   fflush(); next }
  n++; if (n%ev==0)       { print "进度 " line;     fflush() }
  next
}
{ print; fflush() }'
