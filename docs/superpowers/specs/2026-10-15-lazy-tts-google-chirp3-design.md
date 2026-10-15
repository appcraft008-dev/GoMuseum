# 懒生成 TTS 换成 Google Chirp 3 HD(替换 tts-1)

- 日期:2026-10-15
- 状态:用户已确认方案(2026-10-15);独立 review(Sonnet)已过,意见见 §8,已并入
- 出处:backlog 第三节「12 月前换掉 tts-1」;本 spec 取代该行写的「11 月实验 gpt-realtime / gpt-audio-mini」路线

## 1. 为什么要换

OpenAI 2027-01-06 停用 `tts-1` / `tts-1-hd` / `gpt-4o-mini-tts`(10-02 邮件;litellm、OpenAI 社区均有记录),
所以改 `OPENAI_TTS_MODEL` 切到 gpt-4o-mini-tts 也躲不过。官方推荐的 `gpt-realtime-2.1-mini`
不支持 `/v1/audio/speech`,只走 Realtime(WebSocket),且是对话模型、可能改写原文 —— 违背接地原则,不选。

**影响面(prod 只读,10-14)**:tts-1 只用于懒生成兜底。段落音频 tts-1 共 123 段(zh 81 / fr 19 / en 11 /
pl 7 / es 4 / ja 1),VoxCPM2 1 万多段。`llm_usage` tts 通道 10 月 109 次、约 6.6 万字;7 月起累计 151 次 /
约 9.8 万字 → **平均每次约 650 字**。已落 R2 的音频不受停用影响,只是新内容无法即时出声。

VoxCPM2 不能接在线:Mac mini M4 上 RTF 2–4(生成比播放慢 2–4 倍),VPS 无 GPU。

## 2. 选型过程(原始数据保留,供复核)

### 2.1 候选
Google Chirp 3 HD($30/百万字,每月 100 万字免费)、Azure Neural HD($22)、ElevenLabs Flash v2.5($40 + 订阅)、
Amazon Polly(pl/ja 无 Generative 档,淘汰)、Cartesia、MiniMax($60,淘汰)。用户定先比 Google 与 tts-1,不行再看 Azure。
声音克隆(让 Google 直接出 VoxCPM2 音色)不可行:Chirp 3 Instant Custom Voice 要销售白名单 + 声音本人录同意稿,
且跨语言只支持 en-US → de/es/fr/pt,覆盖不了 zh/ja/ko/pl/it。

### 2.2 实验样本
prod 已发布段落,10 语 × 短/中/长(按该语言长度分位 0.2/0.5/0.85 抽)= 30 段(脚本与样本在会话 scratchpad
`ttsab/`,不入库)。tts-1 在 prod 容器内用线上密钥与 `VOICE_MAPPING` 默认音色生成。

### 2.3 中文「句子太长」—— 决定发送方式的关键发现
REST `text:synthesize` 整段送中文会随机返回 `400 This request contains sentences that are too long`,
**同一段文字时好时坏**。逐句探测(3 次/句):单句 ≤63 字 0 失败,81 字的一句 3/3 失败。

| 发法(中文 6 段 × 3 次) | 失败 |
|---|---|
| REST 打包 ≤60 字/请求 | 0/108 请求 |
| REST 打包 ≤120 字 | 24/54 |
| REST 打包 ≤200 字 | 15/33 |
| REST 整段,句间加换行 | 6/18 |
| **gRPC `StreamingSynthesize` 整段一个 input** | 7/18;成功的也可疑:zh 长段只出 61.6s,按句送是 77.4s(疑漏读) |
| **gRPC `StreamingSynthesize` 一句一个 input** | **0/18**,首包 0.16–0.68s;含那句 81 字长句 |

Google 文档对流式输入的建议也是「每个 input 是完整的句子」。→ **一律走流式、按句送**。

**⚠️ 但流式会静默吞掉超长句的句尾(review 后定向查出)**。上表「0/18」只说明不报错;转写核对发现
那句 81 字中文的结尾「形成鲜明对比」在所有流式产出里都没念(按句送 3/3、整段送 3/3、逗号处切成
多个 input 也 3/3 —— Google 会按标点把没有句号的 input 重新拼回一句)。同一句单独送或放在开头则完整。
**修法**:超长句在逗号处切开,并把切点的逗号改成句号(「。」/「.」),3/3 完整。
各语言阈值按实测「最长且未被吞」定:zh/zh-hant **60 字**(63 字未吞、81 字被吞);ja/ko **95 字**
(样本最长 98 未吞);其余 **270 字**(样本最长 276 未吞)。逐句句尾核对(30 段 195 句):除这一句外,
Google 与 tts-1 的句尾缺失数持平(其余均为 whisper 转写噪声,逐条看过)。

### 2.4 码率必须 160 kbps
契约「音频批量生产与灌入」③ + `audio_quality.py`:质量闸用「字节 ÷ 160 kbps」估时长(刻意不调 ffmpeg)。
Google 的 MP3 固定 32 kbps;若落库 32/64 kbps,将来 VoxCPM2 替换它时旧版本时长被估短 5/2.5 倍 →
`deviates_from_existing` 拦下替换。→ 向 Google 要 **PCM 24 kHz**,自己用 `lameenc` 编 **160 kbps 单声道 MP3**。
实测 30/30 过 `check_audio`,`estimate_duration_sec / ffprobe 实际时长` = 1.000。
选 160 是为与质量闸的假设一致,**不是**为匹配 tts-1:现有 123 段 tts-1 实为 128 kbps,替换时按 160 估会短 20%,
在 `REPLACE_MAX_DEVIATION=0.5` 容差内,不处理。

### 2.5 音色与语速
目标是**贴近 VoxCPM2**(懒生成音频以后会被 VoxCPM2 替换,中间期尽量少一次音色跳变)。
参照 = 用户当初定音色时认可的 VoxCPM2 成品 `~/tts-lab/out/FINAL_<lang>.mp3`(《草地上的午餐》Q152509,
原文 `~/tts-lab/texts_prod/guide_<lang>.txt`,与 prod 现行正文长度逐字一致)。14 个 Chirp 3 HD 女声各念一遍,
用 `~/tts-lab/voice_fingerprint.py` 的 ~25 维声学指纹(每语言内 z-score)排距离,前 3 名 + Aoede 进试听页,
**用户逐语言耳选**(10-15)。语速 = 让时长对齐 VoxCPM2 成品。

| 语言 | 声音 | speaking_rate | 指纹名次 |
|---|---|---|---|
| zh | Laomedeia | 1.03 | 4 |
| zh-hant | Despina | 1.02 | 8 |
| en | Autonoe | 1.05 | 1 |
| fr | Callirrhoe | 0.90 | 1 |
| de | Achernar | 0.93 | 1 |
| es | Aoede | 0.98 | 1 |
| it | Autonoe | 1.02 | 1 |
| pl | Kore | 0.97 | 2 |
| ja | Aoede | 0.99 | 2 |
| ko | Erinome | 0.98 | 2 |

locale:zh / zh-hant 都用 `cmn-CN`(Chirp 3 HD 无 `cmn-TW`;现 tts-1 与 VoxCPM2 也是普通话读繁体),
其余 en-US / fr-FR / de-DE / es-ES / it-IT / pl-PL / ja-JP / ko-KR。

### 2.6 最终配置验收(30 段,流式按句 + 160k + 上表)

| 项 | tts-1 | Google 终版 |
|---|---|---|
| 生成成功 | 30/30 | 30/30 |
| 过质量闸 | — | 30/30 |
| 读音真错(whisper-small + `tools/tts/reading_check.analyze`,每千字) | 16.5 | 15.9 |
| 增删字数 | 141 | 83 |
| 时长 / tts-1(各语言 3 段合计) | 1 | 0.91–1.03 |
| 首包 | 1.2–3.4s(prod 服务器测) | 0.13–0.46s(本机测,网络路径不同,只能说同量级、不差) |

**口径说明(review I1)**:每语言 3 段、单次生成、whisper-small 转写,噪声大于组间差;能支持的结论只有
**「整体不比 tts-1 差」**,不说「更好」。分语言数字仅作参考。

分语言真错(每千字,tts-1 → Google):de 10.0→8.2,en 3.1→4.1,es 2.3→28.0,fr 9.1→8.2,it 10.1→9.2,
ja 48.5→43.4,ko 24.2→17.8,pl 32.5→6.0,zh 7.2→13.0,zh-hant 50→55(Despina 3 段 43 处 vs tts-1 39 处 / 约 780 字,几乎全是「居斯塔夫·庫爾貝」被 whisper 转成拉丁字母)。
es 偏高全在 es_short:原文「Mme Vve Jean」被 Google 逐字母念出,whisper 随后陷入重复幻听(转写尾部一串「E.Y.」),计数被放大;tts-1 读成「Mbéjan」也不对,但没触发幻听。属单例,不下结论。
欧语与人名的「真错」多为 whisper 转写噪声(数字、人名转成拉丁字母),两边同尺子,只看相对差。

## 3. 设计

**边界不变**:API 契约、App、`streaming_audio.py`(一次调用 tee 成客户端流 + 整段落 R2)、`lazy_audio.py`、
段级锁、权益闸都不动。只换 `TTSService` 内部的合成实现。属纯后端升级(契约第三类),免发版。

### 3.1 `app/services/tts_service.py`
- 删除 OpenAI 客户端、`VOICE_MAPPING`(OpenAI 音色)、`_speech_kwargs`。
- 新 `VOICES: dict[str, tuple[locale, voice_name, speaking_rate]]` 即 §2.5 表(全名如 `cmn-CN-Chirp3-HD-Laomedeia`)。
  未知语言回落 en(与现行为一致)。
- `split_sentences(text, language) -> list[str]`:在 `。！？` 后、`[.!?]` 后跟空白、以及换行处切;去空白段。
  - 超过该语言阈值(§2.3:zh/zh-hant 60、ja/ko 95、其余 270)的句子在 `，；：,;:、` 处切成不超阈值的块,
    **切点标点改成句号**(CJK「。」、其余「.」)—— 只切不改标点会被 Google 拼回长句、照样吞尾。
    一个块都切不开(无逗号)时按阈值硬切,仍补句号。
  - 拉丁语系 < 12 字符的碎块(如 `St.`、`Mme.` 造成的)并进下一句,避免缩写处断句。
- `_pcm_chunks(text, language)`:**同步** `TextToSpeechClient.streaming_synthesize`(实验验证过的就是同步客户端),
  首个 request 带 `StreamingSynthesizeConfig(voice, StreamingAudioConfig(PCM, 24000, speaking_rate))`,随后每句一个 input;
  逐块 yield PCM。gRPC 调用带 `timeout`(整段 deadline,暂定 60s)。
  客户端按进程懒建(uvicorn `--workers 2`);鉴权 `client_options={"api_key": settings.GOOGLE_TTS_API_KEY}`。
  **不用 `TextToSpeechAsyncClient`(review B1)**:`lazy_audio._synth` 每次 `asyncio.run(...)` 新建事件循环,
  grpc.aio channel 绑定创建时的 loop,跨 loop 复用会炸;同步客户端没有这个问题。
- 异步桥接:`generate_audio_stream` 用 `asyncio.to_thread` 在线程里迭代 `_pcm_chunks`,经 `asyncio.Queue` 交回事件循环,
  做到边收边吐(不阻塞主循环)。
- 编码器包装(review B2,已复现):`lameenc.encode` 收到奇数字节会抛 `Input data must be 16-bit PCM data`,
  没 encode 过就 `flush()` 会抛 `Not currently encoding` → 自己缓冲奇数尾字节留到下一块;PCM 总量为 0 时
  直接抛 `AIServiceException`,不调 `flush()`。
- 结尾自检(review I3):流结束后对整段 MP3 跑 `check_audio(text=..., language=...)`,不过就抛错 →
  `streaming_audio` 走 `persist(None)` 不落库。只能抓「成功但大段缺失」(比例 < 0.45),抓不住几个字的吞尾 —— 那靠上面的切句规则。
- 重试:首块到达前失败,整段重试 1 次;已经吐出音频后失败不重试(客户端已在播,交给 `persist(None)` + 用户重点)。
- `generate_audio_stream(text, language, voice=None, speed=1.0)`:PCM 块喂 `lameenc.Encoder`(160 kbps / 24 kHz / mono),
  有输出就 yield,结尾 yield `flush()`。**签名不变**,`voice`/`speed` 参数保留但忽略(播放倍速在 App 端做)。
- `generate_audio(...)`:收齐 `generate_audio_stream` 返回原 dict 结构(`audio_data`/`content_type=audio/mpeg`/...),
  `voice` 字段填 Google 声音名。超时用 gRPC deadline(同上 60s;实测整段最长 ~12s)。
- `get_supported_voices(lang)`:返回结构不变,`default_voice` 与 `available_voices=[default]` 都是 Google 声音名。
- 用量记账:`record_llm_usage("tts", "google-chirp3-hd", len(text), 0)`(Google 按输入字符计费)。
  `scripts/llm_cost_report.py` 的 `PRICES` 补 `"google-chirp3-hd": (30.0, 0.0)`。
- `generate_text_hash` 也引用了 `VOICE_MAPPING`,改用新表。
- 失败:gRPC 异常包成 `AIServiceException`(现有约定),流式中途失败由 `streaming_audio` 走 `persist(None)` 释放锁、不写 key —— 已有行为。

### 3.2 引擎标记
`content_repo._current_tts_engine()` 返回常量 `"google-chirp3-hd"`(不再读 `OPENAI_TTS_MODEL`)。
`audio_queue` 把非目标引擎视为「待升级」,VoxCPM2 夜跑照常替换,不用改。

### 3.3 配置与依赖
- `Settings` 新增 `GOOGLE_TTS_API_KEY: str = ""`;删 `OPENAI_TTS_MODEL`(若有声明)。`.env.example` 同步。
  ⚠️ 本机已实测:`backend/.env` 里有未声明的键时 `Settings()` 报 `extra_forbidden`。部署侧 compose 用 `env_file`
  注入进程环境变量,是否同样报错未实测 —— 一律**先合代码再加 key**,最稳。
- 依赖:`google-cloud-texttospeech`、`lameenc`(10-15 在 prod 容器内 `pip download lameenc` 拿到
  `lameenc-1.8.4-cp313-cp313-manylinux…x86_64.whl`,即 Python 3.13 / x86_64 有现成 wheel)。
  `poetry add` 后 `poetry lock --check` 通过、CI 镜像构建通过才算数(enrichment-pipeline 教训)。会带进 `grpcio`。
- 密钥:新建一把 API key,只允许 Cloud Text-to-Speech API、应用限制 = IP `38.242.207.219`(prod 与 staging 同机);
  实验用的那把(已在对话里出现过)删除。IP 限制下 gRPC 能否通、VPS 是否走 IPv6 出口,staging 实测时确认。

### 3.4 `/tts/generate`(`content.py`)
外形不变(`TTSRequest.voice/speed` 字段保留以免破老客户端);内部走新实现。App 仍在调它(`content_remote_datasource.dart`),`speed` 被忽略属静默语义变化 → 契约文档写一句(倍速在 App 播放端做)。

## 4. 测试(网络全打桩,单元测试不连 Google)

1. `split_sentences`:中文句号/问叹号、英文 `. ` / `? `、换行(QA 的 `question\n\nanswer` 切成问、答两句)、空串;
   那句 81 字中文被切成 ≤60 字的块且切点变成「。」;ja 96 字、拉丁 271 字同理;无逗号的超长句硬切;
   `St. Peter` / `Mme. Vve` 不在缩写处断开;小数 `1.5`、省略号 `...` 不误切;除切点标点外字符不丢。
2. 160 kbps:打桩 gRPC 吐 N 秒的 PCM 正弦 → 输出 MP3 过 `check_audio`,且 `estimate_duration_sec` ≈ N(±2%)。
   编码器:奇数字节分块输入不抛错且输出与整块输入时长一致;0 字节 PCM 抛 `AIServiceException`。
   结尾自检:打桩只吐 1 秒 PCM 配 1000 字文本 → 抛错,`streaming_audio` 不落库。
3. 每个支持语言都有 `VOICES` 项;locale 与声音名格式正确;zh-hant → `cmn-CN`。
4. 真流式:打桩的 gRPC 迭代器吐第 1 块后挂起 → `generate_audio_stream` 已经 yield 出首块(沿用 `test_tts_true_streaming.py` 的思路,替换掉 OpenAI 版断言)。
5. 首个 request 是 config、之后每句一个 input(断言发送序列)。
5b. 同一个 `TTSService` 在两次 `asyncio.run(generate_audio(...))` 里连续调用都成功(`lazy_audio._synth` 的真实用法)。
5c. 首块前失败重试 1 次;首块后失败不重试、异常抛出。
6. 引擎标记:懒生成落库后 `audio_engine == "google-chirp3-hd"`。
7. `test_tts_service.py` 里断言 `VOICE_MAPPING`、`_speech_kwargs`、`.model == "tts-1"` 的三处改写为新表/新引擎;
   `test_tts_true_streaming.py` 改成打桩 gRPC;`test_tts_endpoint.py`、`tests/unit/api/test_retired_cost_holes.py`
   (打桩 `generate_audio`,签名不变)应原样通过;`streaming_audio` / `lazy_audio` 测试不改。
8. 本地 `black --check`、`isort --check` 手动跑(worktree 里钩子不跑)。

## 5. 上线

1. PR → staging(CI 绿)→ staging 自动部署后,你往 staging env 加 `GOOGLE_TTS_API_KEY`、重启。
2. staging 实测:中/英/法各点一段无音频的段落播放,确认首包、能播、R2 落库、`audio_engine` 标记、`llm_usage` 记账。
3. **上 prod 前加测一轮(review I1)**:用合并后的代码对 zh/en/fr 各 ≥10 段 prod 正文生成,跑读音核对 + 逐句句尾核对,
   与 tts-1 同口径对比;句尾缺失多于 tts-1 就停下查。
4. staging → main 由你合;prod env 加同一把 key、重启。合 main 前确认 prod 没有长任务在跑。

**回滚**:revert 本 PR 即回到 tts-1(2027-01-06 前有效)。新旧音频都在 R2,混存无害。

## 6. 文档
- 契约「音频批量生产与灌入」节补:懒生成引擎 = Google Chirp 3 HD;**任何引擎落库都必须 160 kbps**;声音/语速表在 `tts_service.VOICES`。
- backlog:删「12 月前换掉 tts-1」行,移入最近关闭(带 PR 号)。
- 配方文档 §六「失败方法清单」补:REST 整段送中文随机 400;流式会静默吞超长句句尾(切句时必须把逗号改句号)。

## 7. 不做 / 已知限制
- 不做 tts-1 回退开关(1 月后不可用,留着只是死代码)。
- 不改已落库的 123 段 tts-1 音频(VoxCPM2 队列本来会替换)。
- 德语由 tts-1 男声(echo)变为女声,与 VoxCPM2 一致。
- Google 计费字符口径(CJK 是否按 1 字计)待 staging 跑一周后看账单核实;按现用量,字符数远在免费额度内。
- 流式并发数 / 每分钟请求数配额未核实(现用量每月约百次,不构成约束);上量前查 Cloud Console 配额页。

## 8. 独立 review 处理记录(2026-10-15,Sonnet)

| # | 意见 | 处理 |
|---|---|---|
| B1 | 异步 gRPC 客户端与 `asyncio.run` 每次新建 loop 冲突 | 采纳:改同步客户端 + 线程桥接(§3.1),补测试 5b |
| B2 | `lameenc` 奇数字节 / 空 flush 抛错 | 已复现,采纳(§3.1),补测试 2 |
| I1 | 验收单次跑、噪声大;es 归因不成立;zh_long 疑句界吞字 | 采纳并深查:口径改为「不比 tts-1 差」;**吞字查实是流式吞超长句句尾**,定修法与阈值(§2.3),上 prod 前加测(§5.3)。另:review 把 gs2(Kore 单声音)当成同配置重跑,两次不是同一配置 |
| I2 | tts-1 实为 128k | 采纳,写明不处理的理由(§2.4) |
| I3 | 无结尾自检,成功但缺失的音频会永久落库 | 采纳(§3.1);并说明它抓不住小幅吞尾 |
| I4 | 无超时/重试,锁 TTL 2 分钟后可能重复生成 | 采纳:gRPC deadline 60s + 首块前重试 1 次 |
| I5 | 切句边界(缩写/省略号/QA 换行/阈值无依据) | 采纳:阈值改为实测依据,补缩写合并与测试 |
| I6 | 漏掉 `llm_cost_report` 价目、`generate_text_hash`、具体测试点名 | 采纳 |
| 次要 | 首包口径混杂、配额、IP 限制/IPv6、部署顺序机制、`speed` 静默忽略、lock/black 步骤 | 全部写入对应小节 |
