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

## 三步流程

```bash
# ① VPS 上出队列（后端）
python backend/scripts/audio_queue_cli.py plan \
    --museum orangerie --langs zh,en,fr --engine voxcpm2 --json > jobs.json

# ②a 开跑前预检：正文都取得到吗？这批要跑多久？（契约 ⑪）
python preflight.py jobs.json

# ②b 生成机产文件 —— 用 start_run.sh（它会确认真的跑起来了、并记下起跑 commit）
./start_run.sh jobs.json out_dir 8

# ②c 跑批中看进度（只认 _state.json，别看日志滚动或通知流）
python progress.py out_dir 589

# ③ VPS 上灌入（后端；默认 dry-run，确认后加 --apply）
python backend/scripts/audio_ingest_cli.py --jobs jobs.json --dir ./out_dir --engine voxcpm2
```

⚠️ **必须用 `run_chunked.sh`**：单进程连续跑会 MPS 显存耗尽崩溃
（实测两次：26 段、122 段）。每块起一个新进程即可绕开，不用改模型代码。
契约 ⑥ 有这条，但 2026-09-01 仍然踩了——因为当时它只写在契约里，没写在这。

## 文件

|                    |                                                                                             |
| ------------------ | ------------------------------------------------------------------------------------------- |
| `start_run.sh`     | 起批入口。**日常用这个** —— 它验证进程真的活着才返回，并把起跑 commit 记进日志（契约 ⑯）。  |
| `run_chunked.sh`   | 分块执行（被 `start_run.sh` 调用）。分块是为了绕开 MPS 显存泄漏。                           |
| `run_batch.py`     | 生成主体：拉文本 → 克隆 → 三关质检 → atempo 对齐 → 160k mp3。幂等、断点续传、失败重试 ≤3。  |
| `preflight.py`     | 开跑前预检：每条任务的正文能不能真取到 + 估算成品时长。取不到就别开跑。                     |
| `progress.py`      | 跑批进度快报（读 `_state.json`）：进度、一次过闸率、按语言分布、ETA。                       |
| `fetch_text.py`    | 取正文的**唯一实现**（含 502 重试）。跑批与预检共用，不许再抄第二份。                       |
| `consistency.py`   | 内容一致性打分（纯文本，依赖只有 opencc）。三次静默故障都出在这里。                         |
| `reading_check.py` | **读音级**比对（拼音 / 假名）：区分「ASR 选错字」与「真念错」。分数分辨不了这两件事。       |
| `test_*.py`        | 正负样本自检，CI 每次改动都跑（`reading_check` 的自检用的是已知同音对与已知真错对）。       |
| `fixtures/`        | **真实语料**：prod 讲解原文 + 我们自己音频的实际转写。合成样本测不出 autojunk（配方 §六）。 |

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
