# 交接（前端）：TTS 流式播放（边生成边播）

> 后端已上 **prod**（PR #256，2026-07-16 随 #258 批次发布）。新增**加法端点** `/audio/stream`；
> 老端点 `/audio` 原样未动，已装 APK 零破坏。本交接 = 前端播放器切到新端点，真机体验"点播放几秒内出声"，
> 不再等整段 TTS 生成完（长段可省 10-30s 首播等待）。需重编 prod flavor APK。

## 端点契约

```
GET /api/v1/museums/{slug}/objects/{qid}/audio/stream?language={lang}&section={code}
```

- `section`：`guide` 或深度段（`background`/`analysis`/`facts`/`significance` 等 canonical 段）。
  **`qa` 连念与作者介绍(`artist_bio`)不支持流式**，仍走老 `/audio`（v1 范围，后端注释明示）。
- 无鉴权（与其它内容端点一致）。

### 四种响应（前端必须全处理）

| 情形 | 状态码 | 形状 | 前端动作 |
|---|---|---|---|
| **首次播放（流式）** | 200 | `Content-Type: audio/mpeg`，chunked 字节流 | 渐进播放（见下） |
| **缓存命中（已落库）** | 200 | `Content-Type: application/json`，`{"audio_url": "<R2直链>"}` | 与现状相同：播 R2 URL |
| 同段正在生成（别人先点了） | 409 | `{"detail":{"reason":"audio_generating"}}` | 延时重试（几秒后再 GET，届时大概率变缓存命中）——复用现有 409 重试逻辑 |
| 该段文本未发布 | 404 | `{"detail":{"reason":"no_published_text"}}` | 不显示播放按钮/提示内容生成中 |
| TTS 失败 | 503 | `{"detail":{"reason":"tts_failed"}}` | 现有错误提示 |

⚠️ **同一个 200 可能是 JSON 也可能是音频流** → 不能把 URL 直接丢给播放器就完事，
必须先看 `Content-Type` 分支。

## Flutter 集成模式（建议）

```dart
final rsp = await httpClient.send(http.Request('GET', streamUri)); // 流式发起
final ct = rsp.headers['content-type'] ?? '';
if (ct.contains('application/json')) {
  final url = jsonDecode(await rsp.stream.bytesToString())['audio_url'] as String?;
  // 老路径：just_audio setUrl(R2 直链) —— 与现有播放完全一致
} else {
  // audio/mpeg 字节流：喂给 just_audio 的 StreamAudioSource
  // (或落临时文件边写边播；关键是"首个 chunk 到就开始出声")
}
```

- **StreamAudioSource**：把 `rsp.stream` 的 chunk 递给播放器缓冲。流式响应**无 Content-Length、
  不支持 Range/seek**——首播时进度条只显示已缓冲部分、禁 seek 即可（整段播完或下次播放走 R2 就恢复全功能）。
- **语速档位不变**：仍是客户端播放速率（`setSpeed`），与端点无关。
- **降级安全**：任何流式路径异常（解析失败/播放器不支持）→ 回退调老 `/audio`。
  流式请求即使客户端中途断开，**后端仍会把整段落 R2**（detached 落库），所以回退/重试都会命中缓存,不产生重复 TTS 费用。

## UI 接线点

- 讲解页「听讲解」（guide）与深度抽屉各段的播放按钮 → 换 `/audio/stream`。
- 问答连念、作者介绍播放按钮 → **保持老 `/audio` 不动**。
- 已有的 409 自动重试、播放器进度条组件都可复用；只多一个 Content-Type 分支 + StreamAudioSource。

## 验证清单（真机, prod flavor）

1. 挑一件**还没生成过音频**的对象 → 点播放:应 **~2-5s 内出声**(而非等 10-30s 整段);播完再点 → 走 R2 URL(JSON 分支)。
2. 两台设备同时点同一段 → 后点的收 409 → 自动重试后播缓存。
3. 流式播放中杀 App → 稍后再进,该段应已是缓存命中(后端断连仍落库)。
4. 问答连念/作者介绍 → 行为与现在完全一致(未切流式)。

## 相关

- 后端实现：`backend/app/services/enrichment/streaming_audio.py`（单次 TTS tee：客户端+落库一次调用）、
  `backend/app/api/v1/endpoints/museums.py` `object_audio_stream`。
- 前序交接：`2026-07-06-lazy-tts-streaming-frontend.md`（点播放/409/语速——本交接在其上加流式，不推翻）。
