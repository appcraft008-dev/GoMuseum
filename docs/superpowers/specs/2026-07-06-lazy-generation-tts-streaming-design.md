# 懒生成分层 + 解耦 TTS + 流式先出 设计

**目标（用户定）**：① 大幅省成本；② 降低用户等待时间（**文字和语音都要快**）。

**核心洞察**：内容分两类成本——**英语轴心**（接地生成，慢 ~3-4min、贵、**语言无关可共享**）vs **翻译**（每门 ~40s、便宜、分语言）。钱花在轴心最划算；翻译和 TTS 按真实使用付费。

---

## 三条原则

1. **钱花在英语轴心**：轴心贵且被所有语言共享 → 预热预算砸轴心；翻译/TTS 按需。
2. **每一层 guide 先出（流式）**：轴心生成先落 guide、翻译先翻 guide、前端 guide 一到就显示——砍首屏等待。
3. **只为真实使用付费**：语言按请求生成、TTS 按播放生成、语速客户端调（零成本）。

## 架构：三层懒生成

```
英语轴心(guide→深度→QA,接地)   ── 造一次,全语言共享;guide 先落库
    │  guide 一好,任意语言即可翻译
    ├─ 语言翻译(guide→深度→QA)   ── 该语言首次请求触发;guide 先翻先显
    │      │                        有轴心 → guide ~10s;无轴心 → +轴心3-4min
    │      └─ TTS 音频(仅 guide)   ── 用户点"播放"才生成(解耦),段级落库复用
    └─ 语速 0.75/1/1.5/2x          ── 客户端 setPlaybackRate,一个音频文件,零成本
```

## 两个场景

| 场景 | 内容 | TTS |
|---|---|---|
| **① 上线预热**（`generate`，**per-language N**） | 见下 per-language N | 预热语言的 guide 可选预生成 |
| **② 懒生成**（识别命中/点击，日常） | **只请求语言**（有轴心~10s流式，无则+3-4min） | 点播放才生成 guide 音频 |

**per-language N 配置（想法1）**：`generate --limit N --langs <lang>` 按语言分别配额。
- **英语轴心 N 拉高**（如 N_en=100-200）：预热覆盖 top-N 件的**所有语言**（有轴心后各语言懒翻译仅 ~10s）。
- **展示语言默认 N=0**：有轴心后懒翻译够快，不值得预付。
- **例外**：主力观众语言可配小 N（如某馆 zh=50）→ 主力用户零等待。
- **现状 N=0 全休眠**（prod 内容保持空，用户手动测试期）；将来设 N_en>0 即启用。

## 组件与改动

### 1. 懒生成改单语言（复用现有基础设施）
- `run_lazy_generation`（现"全语言"）→ 生成**英语轴心 + 请求语言**（不再全 10 语）。
- 后续语言交给**已存在的** `run_lazy_translation`（单语言，~40s/门，费用分钱级）。
- `maybe_trigger` 分流不变（stub→生成、ready 缺语言→翻译）。改动集中在 `generate_object` 的 `target_langs`：懒路径传 `[en, request_lang]` 而非全集。

### 2. guide 先出流式（想法2，贯穿两层）
- **英语轴心**：`generate_object` 现已先造 `guide_text` 再造深度模块；改**持久化为增量**——guide 生成即 `persist`，再造+持久化深度模块、QA（现在是最后一次性 persist）。
- **语言翻译**：`translate_object` 逐段翻译时 guide 段**优先翻+持久化**，深度/QA 随后（现已逐段，只需保证 guide 段排首 + 翻完即落）。
- **前端状态细化**：content 端点 `generating=true` 且 `default_guide` 已存在 → 前端**显示 guide + "深度内容生成中"**，继续轮询;深度模块/问答到了填入。（现有三态加一个"部分就绪"分支——guide 在 + generating。）

### 3. TTS 懒生成端点（仅 guide）
- 新端点：`GET /museums/{slug}/objects/{qid}/audio?language=X&section=guide`
  - 有 `audio_key`（`get_section_audio_key`）→ 秒返 R2 URL。
  - 无 → `TTSService.generate_audio(guide_body, X)` → `persist_section_audio`（传 R2+写 audio_key）→ 返 URL。
  - 段级轻锁防同段同语言并发重复生成（复用懒锁思路，attributes 或 section 级）。
- **VOICE_MAPPING 补 ja/ko/zh-hant**（现只有老语言；新语言需加音色，OpenAI tts-1 支持的通用音色即可）。
- 失败：返明确错误码，不写 audio_key（现有"失败不落库"保证已在）；前端"音频暂不可用"可重试，**不阻塞文字**。
- 正文变更→旧音频失效（现有 `audio_key=None` on body change 已在）。

### 4. 语速客户端化
- 一个音频文件（1x 生成），前端播放器 `setPlaybackRate(0.75/1/1.5/2)`。**零后端改动、零生成成本**。legacy 识别路径已有 `_speeds` 雏形可复用。

## 数据流（用户点一件无内容藏品，请求 zh）

```
点击 → content 端点 maybe_trigger
  ├ 轴心不存在 → 生成英语轴心:guide 先落(~1-2min) → 深度/QA 随后
  │              前端:generating=true,guide 一落显示英文? 否——等 zh
  ├ 翻译 zh:guide 先翻先落(~10s) → 前端显示 zh guide + "深度生成中"
  │         深度模块/问答 zh 随后流式填入
  └ 用户点"听讲解" → audio 端点:无key→生成 zh guide 音频(~数秒)→播放
                    语速按钮:客户端 0.75~2x
第二个用户请求 ja(同件) → 轴心已在 → 只翻 ja guide~10s流式 + 点播放才出 ja 音频
```

## 内容状态 / 列表

- 列表语言感知状态（已实现）：某语言未发布→显"待完善/生成中"。单语言懒生成后该语言转 ready。不受本设计破坏。
- `content_status` 对象级仍为 ready（英语轴心在即 ready）；per-language 就绪看该语言 published 段（已实现）。

## 错误处理 / 边界

- 单语言翻译失败：该语言 needs_review 隐藏（宁缺毋滥,现有）；不影响其他语言/轴心。
- TTS 失败：不落 audio_key、返错误、前端可重试、不挡文字。
- 并发防重：内容懒锁（现有 TTL）；TTS 段级轻锁（新）。
- 忠实度/接地不变——TTS 只念已发布文字。

## 测试

- 懒生成只产 `[en, request_lang]`，不产其他语言（断言其他语言无 published 段）。
- guide 先于深度模块持久化（顺序断言：轮询中间态 guide 在、深度缺）。
- 单语言翻译（有轴心）：只补该语言、~guide 先落。
- TTS 端点：无 key→生成+落库+返 URL；有 key→秒返不重生成;失败→不写 key。
- per-language N：`generate --langs en --limit 2` 只生成 en 轴心不翻译；`--langs zh` 补 zh。
- 语速：纯前端，无后端测试。
- 全链路 e2e（staging）：点击→guide 流式→切语言→TTS 播放。

## 成本 / 等待对比

| | 现状（全语言） | 本设计 |
|---|---|---|
| 一次触发成本 | 英语轴心 + 10 门翻译 | 英语轴心 + 1 门翻译（省 9 门） |
| 用户看到 guide | ~4-5min（轴心+翻译全段） | 有轴心 ~10s / 无轴心 ~1-2min（guide 先出） |
| 第二语言用户 | 秒开（已预生成） | ~10s（轴心在,懒翻译 guide） |
| TTS | 无 | 点播放~数秒,落库复用;语速零成本 |

**代价**：第二语言用户从"秒开"变"~10s"，换取省 9 门无人看的翻译 + 只为真听的音频付费。10 语时非常划算。

## 分期

- **Phase 1**（本设计核心）：懒生成单语言 + guide 先出流式（两层）+ TTS 懒端点(guide) + VOICE_MAPPING 补三语 + 语速客户端。
- **Phase 2**（留接口，暂不实现）：per-language N 预热的 TTS 预生成、深度模块/问答的 TTS。
- per-language N 的 generate 配额：Phase 1 实现（`--langs` 已支持），保持 N=0 休眠。

## 前端交接（另出 handoff）
- 部分就绪状态（guide 在 + generating→显 guide + "深度生成中"）
- "听讲解"点播放→调 audio 端点→播放；生成中转圈
- 语速档位 0.75/1/1.5/2x（setPlaybackRate）
