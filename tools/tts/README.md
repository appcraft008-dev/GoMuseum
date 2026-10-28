# 自托管 TTS 批量生成（VoxCPM2）

跑在**生成机**（Mac mini M4）上，不在后端容器里。这里只产 mp3 文件，
**不碰 DB、不碰 R2 凭证** —— 落库由 `backend/scripts/audio_ingest_cli.py` 负责。
分工与文件名约定见契约 `docs/architecture/museum-api-contract.md`
「音频批量生产与灌入」；调参配方（种子、cfg、音色指标）见
`docs/architecture/tts-voice-production-recipe.md`。

## 为什么这些脚本在仓库里

生成侧出错的后果不是「跑挂了」，而是**静默毁掉内容库**：判定函数一旦失灵，
会一边烧算力、一边把合格内容永久标成失败，而且看起来一切正常。
这类缺陷已经发生三次（autojunk、漏归一化、日语浊点），
每次都是靠人工比对才发现的。放进版本控制 + 配自动测试，是为了让第四次被挡住。

## 多批排队与暂停(2026-10-28)

多批串行用 `queue.sh`,批次仍由 `start_run.sh` 起:

```bash
tools/tts/queue.sh start    # 按 ~/tts-lab/queue.txt 逐批跑,已完成的批次跳过
tools/tts/queue.sh pause    # 让出资源:先停队列再停批次,正在生成的那 1 条作废
tools/tts/queue.sh status   # 每批 完成/未完成 + 条数
```

`~/tts-lab/queue*.txt` 每个文件一条串行队列,start/pause/status 默认一次管全部;
文件名含 `modal` 的(如 `queue_modal.txt`)生成放 Modal,与 Mac 队列并行。Modal 队列
必须在沙箱外起(沙箱内连不上 input-plane);月度花费上限设在 Modal 后台 usage limit。
每行「<jobs.json> <输出目录>」。完成与否只认日志里本次起跑后的 ALLDONE
—— 被 pause 杀掉的批次没有它,队列会停在原地,而不是当成跑完去起下一批
(10-26 手搓串联就这样让意语提前开跑过)。续跑 = 再 `start`,批内已合格的条目自动跳过。

## 唯一管线(2026-10-25 定)

**生成只有这一份代码、这一个入口:`tools/tts/start_run.sh`。** 要改进就改这里、走 PR,
不许在别处复制一份改。生成机的 `~/tts-lab` 只放种子、任务文件和输出目录,不放脚本。

为什么:10-19 起有批次绕开这里、直接跑了生成机上 8 月底的旧副本
(`~/tts-lab/run_batch.py`,没有响度归一、zh-hant 喂繁体、不记 md5),
535 条照样灌进 prod,线上响度极差 12.1dB;同期仓库版产的 11999 条极差 0.1dB。

三道机器闸保证走错路的产物上不了线:

1. `start_run.sh`:`tools/tts` 有未提交改动 → 拒绝起跑(保证记下的 commit 就是实际代码);
2. 每条 `_state.json` 记录写 `pipeline`(起跑 commit)与 `md5`;
3. 灌入端:记录缺 `md5`/`pipeline` → 拒绝落库(老批次重灌显式 `--allow-legacy-state`)。

日志里每次起跑都有一行 `=== 起跑 … commit xxxx ===`,**没有这行就是走错了入口。**

## 三步流程

```bash
# ① VPS 上出队列（后端）
python backend/scripts/audio_queue_cli.py plan \
    --museum orangerie --langs zh,en,fr --engine voxcpm2 --json > jobs.json

# ②a 开跑前预检：正文都取得到吗？这批要跑多久？（契约 ⑪）
python preflight.py jobs.json

# ②b 生成机产文件 —— 用 start_run.sh（它会确认真的跑起来了、并记下起跑 commit）
./start_run.sh jobs.json out_dir 8
#    或把生成放到 Modal L40S(fp32,约 Mac 5 倍速、每 1000 条约 $22;质检仍在本机):
TTS_GPU=modal MAX_USD=10 ./start_run.sh jobs.json out_dir

# ②c 跑批中看进度（只认 _state.json，别看日志滚动或通知流）
python progress.py out_dir 589

# ③ VPS 上灌入（后端；默认 dry-run，确认后加 --apply）
python backend/scripts/audio_ingest_cli.py --jobs jobs.json --dir ./out_dir --engine voxcpm2
```

⚠️ **必须用 `run_chunked.sh`**：单进程连续跑会 MPS 显存耗尽崩溃
（实测两次：26 段、122 段）。每块起一个新进程即可绕开，不用改模型代码。
契约 ⑥ 有这条，但 2026-09-01 仍然踩了——因为当时它只写在契约里，没写在这。

## 文件

|                    |                                                                                                                                                                |
| ------------------ | -------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `start_run.sh`     | 起批入口。**日常用这个** —— 它验证进程真的活着才返回，并把起跑 commit 记进日志（契约 ⑯）。                                                                     |
| `run_chunked.sh`   | 分块执行（被 `start_run.sh` 调用）。分块是为了绕开 MPS 显存泄漏。                                                                                              |
| `run_batch.py`     | 生成主体：拉文本 → 克隆 → atempo 语速对齐 → 响度对齐 → 三关质检 → 160k mp3。幂等、断点续传、≤3 次尝试；合格但节奏偏(atempo 出 0.80-1.00)会再试，留最匀的那条。 |
| `preflight.py`     | 开跑前预检：每条任务的正文能不能真取到 + 估算成品时长。取不到就别开跑。                                                                                        |
| `progress.py`      | 跑批进度快报（读 `_state.json`）：进度、一次过闸率、按语言分布、ETA。                                                                                          |
| `fetch_text.py`    | 取正文的**唯一实现**（含 502 重试）。跑批与预检共用，不许再抄第二份。                                                                                          |
| `consistency.py`   | 内容一致性打分（纯文本，依赖只有 opencc）。三次静默故障都出在这里。                                                                                            |
| `reading_check.py` | **读音级**比对（拼音 / 假名）：区分「ASR 选错字」与「真念错」。分数分辨不了这两件事。判日语先看 `read_consistency`（整段注音），不要只看片段归类出来的真错率。 |
| `test_*.py`        | 正负样本自检，CI 每次改动都跑（`reading_check` 的自检用的是已知同音对与已知真错对）。                                                                          |
| `fixtures/`        | **真实语料**：prod 讲解原文 + 我们自己音频的实际转写。合成样本测不出 autojunk（配方 §六）。                                                                    |

## 判效果用读音级比对，不要用一致性分数

判「重灌 / 换种子 / 改预处理有没有效」时，一致性分数**做不到**：
「盗」→「到」（同音，音频是对的）和「夕阳」→「的棋羊」（真念错）被一视同仁地扣分。

```bash
python reading_check.py jobs.json out_new [out_old]    # 给了旧目录就是 A/B
```

⚠️ 仪器有底噪：日语侧拿**已接受的 tts-1 基准**量过，真错率约 45/千字。
低于底噪的差异说明不了任何事。
⚠️ 挑样本别按分数挑 —— 2026-09-09 实测会得出**反向**结论（选择偏差）。

## 环境变量

- `TTS_LAB`：种子目录 `seeds_final/` 的父目录，默认为本文件所在目录。
- `GOMUSEUM_API`：取文本的 API 基址，默认 prod。

种子文件 `seeds_final/SEED_zh.wav` / `SEED_en.wav` 是二进制且体积大，**不入库**，
留在生成机上；丢失时按配方 §五 重新产出。

## 改动纪律

改 `consistency.py` 前先读契约纪律 14 / 18 / 25。改完必须：

1. `pytest test_consistency.py` 全绿；
2. **把修复撤掉看测试会不会红** —— 不红就是假测试（纪律 16）；
3. 按纪律 18 用新函数**重跑全量**，不得手工放行旧结果。
