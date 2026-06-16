# TTS 音频落库收口 — 设计文档

> 创建于 2026-06-16。富化管线 v1 的地基收口：补齐"音频落库"这一环，
> 堵掉每次播放重付 OpenAI TTS 的成本漏洞。对称已完成的"讲解落库"
> （`persist_explanation`）。

## 1. 背景与问题

GoMuseum 有两条并行的内容通道：

1. **实时讲解流**：App → `POST /api/v1/content/explanation`（生成讲解）
   + `POST /api/v1/content/tts/generate`（生成音频）。传原始文本，临时。
2. **藏品内容流**：App → `GET /api/v1/museums/{slug}/objects/{qid}/content`
   → `museum_repo.get_object_content` → 从 `object_content_sections` 读
   `body` + `audio_url`（`audio_url = storage.public_url(audio_key)`），持久。

**讲解**已经闭环：`/content/explanation` 端点在带 `qid` 且非兜底时调
`content_repo.persist_explanation` write-through 落库到 `object_content_sections.body`。

**音频**没闭环：`/content/tts/generate` 生成 mp3 后直接 `StreamingResponse`
流给用户，**既不上传 R2、也不写 `audio_key`**。`tts_service` 只生成 bytes。
后果——`museum_repo` 的 `audio_url` 读路径**悬空**（无人写 `audio_key`），
且每次播放都重新调 OpenAI TTS **重付费**、重部署即丢。

`object_content_sections` 表结构已就绪（`body` + `audio_key` nullable +
唯一键 `(object_id, language, section_code)`），R2 已配进 staging/prod。
缺的只是"生成→落库"这一环。

## 2. 目标与非目标

**目标**：section 维度的音频持久化（write-through R2 + `audio_key`），
replay 复用已存音频，零重复 OpenAI 调用。

**非目标**（留给后续"内容做厚 / 第②步"）：
- 批量预生成音频（离线 CLI 一次性灌全馆）。
- 多 voice / 多语速的持久化。
- 讲解内容本身的批量 grounded 生成。

## 3. 触发模型

**懒写 write-through**，对称 `persist_explanation`：用户实时请求音频时，
首次生成即落库，再次请求直接返回已存 `audio_url`。不做批量预生成
（那是第②步）。

## 4. 组件与职责

- **`tts_service`（不动）**：保持"纯生成 bytes"，不掺存储逻辑。
- **`content_repo` 新增 `persist_section_audio(db, qid, language, section_code,
  audio_bytes) -> str`**：与 `persist_explanation` 同居一处。
  upsert `object_content_sections` 行（行不存在则建，`body` 可为空），
  把 `audio_bytes` 上传 R2 得到 key、写入该行 `audio_key`、commit，返回 `audio_key`。
- **`content_repo.persist_explanation`（改）**：写入新 `body` 且与旧 `body`
  不同时，顺手把该行 `audio_key=None`（失效旧音频）。`body` 未变则保留。
- **`/content/tts/generate` 端点（改为双模）**：
  - **section 模式**（请求带 `qid` + `section_code`）：先查该 section 是否已有
    `audio_key`——有则直接返回 `{"audio_url": ..., "cached": true}`（零 OpenAI 调用）；
    无则 `tts_service.generate_audio` 生成 → `persist_section_audio` 落库
    → 返回 `{"audio_url": ..., "cached": false}`。
  - **ad-hoc 模式**（无 `qid`/`section_code`）：**保持原样** `StreamingResponse`
    流式返回 mp3（向后兼容，自定义 voice/speed 走这条）。
- **读路径 `museum_repo.get_object_content`（不动）**：已从 `audio_key`
  返回 `audio_url`。

## 5. 设计决策（已定）

- **R2 key 方案**：`object-audio/{qid}/{language}/{section_code}.mp3`。
  按 `(qid, language, section_code)` 稳定命名，重生成即覆盖（不留孤儿文件）。
- **声音/语速规范化**：section 模式只生成**规范版**——该语言默认 voice
  （`VOICE_MAPPING[language]["default"]`）+ `speed=1.0`，忽略请求里的自定义
  voice/speed。保证每段只有一个无歧义 `audio_url`。自定义 voice/速度的需求
  走 ad-hoc 流式模式，不落库。
- **R2 上传失败处理**：上传未成功**绝不写 `audio_key`**（不留指向缺失对象的
  悬空指针），端点返回 500。
- **section 行不存在**：`persist_section_audio` upsert——行缺失则新建
  （`body=None`、`audio_key=<key>`）。`museum_repo` 分别读 `body` 与 `audio_key`，
  故"有音频无 body"的行对音频 tab 可用、无副作用。

## 6. 数据流（section 模式）

```
App → POST /api/v1/content/tts/generate {qid, language, section_code, text}
  ├─ 该 section 已有 audio_key
  │     → 返回 {audio_url: public_url(audio_key), cached: true}   # 零 OpenAI 调用
  └─ 无 audio_key
        → tts_service.generate_audio(text, language)              # 规范 voice + speed 1.0
        → storage.put("object-audio/{qid}/{language}/{section}.mp3", bytes, "audio/mpeg")
        → content_repo.persist_section_audio 写 audio_key, commit
        → 返回 {audio_url: ..., cached: false}
```

ad-hoc 模式（无 qid/section）流程与现状完全一致，返回 `StreamingResponse`。

## 7. API 契约

**请求**（`TTSRequest` 扩展，新增可选字段 `qid` / `section_code`）：
```jsonc
// section 模式
{ "text": "...", "language": "zh", "qid": "Q123", "section_code": "overview" }
// ad-hoc 模式（现状，向后兼容）
{ "text": "...", "language": "zh", "voice": "...", "speed": 1.2 }
```

**响应**：
- section 模式 → `application/json`：`{ "audio_url": "https://pub-....r2.dev/object-audio/...", "cached": true|false }`
- ad-hoc 模式 → `audio/mpeg` 流（现状不变）。

模式判定：`qid` 且 `section_code` 同时存在 → section 模式；否则 ad-hoc。

## 8. 错误处理

| 场景 | 行为 |
|---|---|
| TTS 生成失败（`AIServiceException`） | 500，不写 DB / R2 |
| R2 上传失败 | 500，**不写 `audio_key`**（避免悬空指针） |
| `qid` 在库中不存在 | 404 `{"error":"ObjectNotFound"}` |
| ad-hoc 模式任意失败 | 现状行为不变 |

## 9. 前端改动（范围内，最小）

`content_remote_datasource.dart` 的 TTS 调用：section 模式下解析
JSON `audio_url`（交给 `audioPlayer.setUrl`），不再消费字节流。
guide 流在已知 `qid`/`section` 时带上这两个字段。ad-hoc 调用不变。

## 10. 测试

**后端单元**：
- `persist_section_audio`：① 已有 audio_key → 复用、不调 TTS、不传 R2；
  ② 无 → 生成+上传+写 key（mock tts_service + storage）；
  ③ R2 上传抛错 → 不写 audio_key、异常上抛；④ section 行不存在 → upsert 新建。
- `persist_explanation`：① body 变 → `audio_key` 置空；② body 未变 → `audio_key` 保留。
- 端点：① section 模式返回 `{audio_url, cached}` JSON；
  ② ad-hoc 模式返回 `StreamingResponse`；③ 复用路径 `cached:true` 不触发生成。

**前端单元**：
- datasource：section 模式解析 `audio_url`；ad-hoc 模式仍走字节流。

## 11. 验收标准

- 同一 `(qid, language, section_code)` 第二次请求音频 → `cached:true`、
  无 OpenAI TTS 调用、`audio_url` 指向 R2。
- 音频对象真实存在于 R2（`storage.exists(audio_key)` 为真）。
- `museum_repo` 的 `object_content` 在音频已落库后返回非空 `audio_url`。
- 讲解 body 重生成后，旧 `audio_key` 被清空，下次请求重生成音频。
- ad-hoc 模式（无 qid/section）行为与改动前完全一致。
