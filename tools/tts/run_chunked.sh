#!/bin/bash
# 分块跑,每块一个新进程 —— 绕开 MPS 内存泄漏(实测连续26段后OOM)
JOBS=$1; OUT=$2; CHUNK=${3:-10}
TOTAL=$(~/tts-lab/venv/bin/python -c "import json;print(len(json.load(open('$JOBS'))))")
for ((i=0; i<TOTAL; i+=CHUNK)); do
  ~/tts-lab/venv/bin/python -c "
import json,sys
d=json.load(open('$JOBS'))[$i:$i+$CHUNK]
json.dump(d, open('/tmp/_chunk.json','w'), ensure_ascii=False)
print(f'--- 块 {$i}-{min($i+$CHUNK,$TOTAL)} / $TOTAL ---')
"
  ~/tts-lab/venv/bin/python ~/tts-lab/run_batch.py /tmp/_chunk.json "$OUT" 2>&1 | grep -E "^\[|完成|无文本|Error"
done
echo "ALLDONE"
