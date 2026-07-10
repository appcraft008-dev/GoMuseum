# 交接（前端）：懒生成流式先出 + TTS 点播放 + 语速档位

> 后端已上（staging 待部署）：懒生成改单语言（省成本）、guide 先出流式（降等待）、TTS 懒生成端点（点播放触发，仅 guide）。
> 前端三件：① 部分就绪流式显示 ② 听讲解点播放 ③ 语速档位。均加法，老行为不破。

## ① 部分就绪流式（细化现有三态）

后端现在 **guide 先落库**，深度模块/问答随后。所以会出现「`generating=true` 但 `default_guide` 已有」的中间态。

- 判断顺序：**先看 `default_guide` 是否有 body**。
  - `default_guide.body` 有 → **立即显示主讲解**（不管 generating）；若同时 `generating=true`，在深度内容区显示轻提示「深度内容生成中…」，继续轮询；深度模块/问答到了填入。
  - `default_guide` 空 + `generating=true` → 现有「生成中」转圈。
  - `default_guide` 空 + `generating=false` → 现有「资料不足/待完善」三态。
- 效果：用户 ~10s（有轴心）或 ~1-2min（无轴心）就看到主讲解，不用等全部 4-5 分钟。

## ①b 等待进度（诚实分数 + 阶段 + 计时，⛔不做假进度条）

⚠️ **不要做时间百分比/匀速进度条**——LLM 生成时间不可预测（30s~4min），假进度条会卡在 90% 反伤信任。用**诚实的三样**：

1. **阶段文字**：guide 未出→「正在生成讲解…」；guide 出+`generating=true`→「主讲解已就绪，深度内容生成中…」。（前端零后端）
2. **真实段落分数**：content 端点新增 `generation: {published, expected}`（加法字段）——显示「深度内容 `published`/`expected` 段」。这是唯一诚实的"进度"，随轮询真实增长。
3. **计时 + 预期**：「已等 45 秒，通常 1-3 分钟」（前端本地计时）。

## ①c 语音生成等待

TTS 只需 ~数秒 → **spinner 即可**，别加进度条（过度设计）。点「听讲解」后转圈到 `audio_url` 返回。

## ② 听讲解点播放（TTS 懒生成，仅 guide）

- 端点：`GET /api/v1/museums/{slug}/objects/{qid}/audio?language={lang}&section=guide`
  - 200 `{ "audio_url": "<R2 URL>" }` → 播放。
  - 首次点击会现场生成（~数秒），显示 loading；生成后落库，之后所有同语言用户秒回。
  - **404** `{reason: no_published_text}`：该语言 guide 文字还没生成（还在懒生成中）→ 提示「讲解生成后可听」，不报错。
  - **503** `{reason: tts_failed}`：音频生成失败 → 「音频暂不可用，请重试」，**不阻塞文字**。
- `language` 用 API 语言参数（繁体记得发 `zh-hant` 非 `zh`，见三语交接的 apiLanguage 映射）。
- 深度模块/问答音频 = Phase 2，暂不做。

## ③ 语速档位 0.75 / 1 / 1.5 / 2x

- **一个音频文件**，四档是**客户端播放器 `setPlaybackRate`**——不重新请求、零后端成本。
- legacy 识别路径已有 `_speeds = [1.0, 1.25, 1.5, 0.75]` 雏形，可参考改成 0.75/1/1.5/2。
- UI：播放条上加档位切换（如点按循环或下拉）。

## 验收

- 点开一件未富化藏品：先转圈 →（~10s 或分钟级后）**主讲解先出**、深度内容区「生成中」→ 深度/问答陆续填入。
- 「听讲解」点击 → loading → 播放；再点秒回（已落库）。
- 语速切 2x → 立即变速、无重新加载。
- 未生成语言点听讲解 → 友好提示不报错；音频失败 → 可重试、文字不受影响。

## 相关
- 契约：`docs/architecture/museum-api-contract.md`（generating 字段/懒生成）
- 设计/计划：`docs/superpowers/specs/2026-07-06-lazy-generation-tts-streaming-design.md`
- 三语 apiLanguage 映射：`docs/handoff/2026-07-06-three-nonlatin-languages-frontend.md`
