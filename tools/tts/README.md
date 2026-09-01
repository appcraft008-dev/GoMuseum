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

# ② 生成机产文件 —— 必须走 run_chunked.sh，不要直接调 run_batch.py
./run_chunked.sh jobs.json out_dir 10

# ③ VPS 上灌入（后端；默认 dry-run，确认后加 --apply）
python backend/scripts/audio_ingest_cli.py --jobs jobs.json --dir ./out_dir --engine voxcpm2
```

⚠️ **必须用 `run_chunked.sh`**：单进程连续跑会 MPS 显存耗尽崩溃
（实测两次：26 段、122 段）。每块起一个新进程即可绕开，不用改模型代码。
契约 ⑥ 有这条，但 2026-09-01 仍然踩了——因为当时它只写在契约里，没写在这。

## 文件

|                       |                                                                                             |
| --------------------- | ------------------------------------------------------------------------------------------- |
| `run_batch.py`        | 生成主体：拉文本 → 克隆 → 三关质检 → atempo 对齐 → 160k mp3。幂等、断点续传、失败重试 ≤3。  |
| `run_chunked.sh`      | 分块入口。**日常用这个。**                                                                  |
| `consistency.py`      | 内容一致性打分（纯文本，依赖只有 opencc）。三次静默故障都出在这里。                         |
| `test_consistency.py` | 正负样本自检，CI 每次改动都跑。                                                             |
| `fixtures/`           | **真实语料**：prod 讲解原文 + 我们自己音频的实际转写。合成样本测不出 autojunk（配方 §六）。 |

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
