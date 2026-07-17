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

---

## ⚠️ Addendum（2026-07-17）：#262 真机实测未达标——三处待修

> 实测环境：staging 编译连 prod 的 APK,《草地上的午餐》(Q152509) 10 语 guide 逐一点播放。
> **后端已排除**：prod 日志确认 `/audio/stream` 返 200、真流式吐 chunk、tee 落库正常("TTS audio stream completed"),无 5xx。
> **问题全在前端播放侧**：大部分语言等 18-25s(≈整段生成时间)才出声;ja 等 >40s 报失败,再点 ~10s 播出。

### 症状 ↔ 日志证据 ↔ 根因

| # | 症状 | 日志证据(prod, 2026-07-16 21:2x UTC) | 根因/嫌疑 |
|---|---|---|---|
| 1 | **等待≈整段生成时间,"首 chunk 出声"没发生** | ko:stream 请求 21:27:28 → 生成完 21:27:48(20s),用户等了 ~20s;且 ko/zh-hant **流式 200 之后又出现老 `/audio` 请求** = `_startWith` 失败走了 `_loadLegacy` 降级 | `guide_audio_player.dart` `_player.setAudioSource(source).timeout(35s)`——真机上 setAudioSource **等到流结束才 ready(或失败)**。需 adb logcat(ExoPlayer tag)查它在等什么;方向:首 chunk 到即 ready 的正确姿势(先 play 再等 ready / ExoPlayer 缓冲参数 / `TtsChunkAudioSource` 的 request 响应形状) |
| 2 | **ja 等 >40s 失败** | ja 生成异常慢(chunk 吐了 2min17s:21:24:28→21:26:45);客户端 ~35-40s 处断开;后端 detached 照常落完库 → 用户再点命中缓存 ~10s 播出 | `catalog_remote_datasource.dart` `getGuideAudioStream` 沿用了 **`receiveTimeout: 35s`**(那是老端点"同步生成 3-8s"的参数)——流式连接本来就要挂 1-2 分钟,中途撞超时 → DioException → 报失败。**修:流式请求去掉或放宽到 ≥120s**(或仅对"首 chunk 未到"设短超时) |
| 3 | **降级链 409 风暴** | ja 失败后老 `/audio` 每 2s 一发连打 15+ 次,再叠 `/audio/stream` 重试——两端点抢同一段级锁互撞 | 流式失败 → `_loadLegacy` 的 2s 固定重试,叠加流式自身重试。**修:降级重试指数退避(2s→4s→8s…),且同段同时只允许一条在途请求** |

### 修复验收（对着本文验证清单第 1 条,当前不达标）

- **长文本语言(ja/ko)点播放 ≤5s 出声**(这是流式存在的全部意义;18-25s = 和不做流式一样);
- ja 类慢生成(>1min)不再报失败,持续渐进播放;
- 抓包/日志确认:单次播放**只出现 `/audio/stream` 一条在途请求**,无老端点连打。

> 提示:后端锁行为——流式生成期间任何端点再请求同段都是 409,**409 重试属正常**;要修的只是节流与"流式明明成功却降级"。

---

## ⚠️ Addendum 2（2026-07-17）：后端真流式上线后,播放器静音——TtsChunkAudioSource 增量喂数据 bug

> 症状(真机,prod):点播放 → 1-2s 停止转圈(进入 loaded 态)→ **完全无声**。
> 背景:#269 修复后端假流式已上 prod(此前 `speech.create()` 缓冲整段;现 `with_streaming_response` 真渐进)。

### 证据链:后端已彻底排除,问题在播放器

| 检查 | 结果 |
|---|---|
| 服务端首 chunk(prod 逐 chunk 计时) | 4.30s 到,其后持续渐进吐完 ✅ |
| 用户测试时间线(Q1565086/Q3879260, 00:33-00:34 UTC) | stream 200,客户端把整条流读完(连接保持到 completed),**无降级无报错** ✅ |
| 落库 R2 文件 | 两件都 200、valid MP3(magic 0xFFF3E4) ✅ |
| 播放 | ❌ 静音 |

### 关键洞察:昨天能响、今天哑了,差别只有"数据到达方式"

- **昨天(假流式)**:9-14s 等待后字节**一次性全到** → `TtsChunkAudioSource` 拿到完整 buffer → ExoPlayer 播放正常;
- **今天(真流式)**:字节**逐步到达** → 同一个源静音。
- ⇒ `TtsChunkAudioSource` 的"增量喂数据"路径**此前从未被真正走过**,bug 藏在这条路上(spinner 1-2s 停 = `setAudioSource` 在首批数据到达时过早 resolve,随后 ExoPlayer 卡死/吞错)。

### 排查方向(按性价比排序)

1. **先隔离**:重点同一段(已缓存)再点一次 → 走 R2 直链分支。响 = 播放栈正常,bug 只在流式源;
2. **别吞错**:`_startWith` 的 `catch (_)` 和播放器错误全被吞——挂 `_player.playbackEventStream`/`errorStream` 监听打日志,`adb logcat`(ExoPlayer/AudioTrack tag)看真机错误;
3. 观察 `position`/`processingState`:是 `buffering` 卡死(缓冲阈值/数据饥饿)还是 `ready` 但 AudioTrack 没起;
4. 检查 `TtsChunkAudioSource.request()` 的增量语义:`contentLength/sourceLength=null` + 增量 `_emit` 与 just_audio proxy/ExoPlayer 的兼容性(首批数据后 proxy 是否重复 request?`start` 非 0 的二次请求是否被正确服务?);
5. **稳妥备选(若 4 难缠,建议直接换)**:放弃自定义 StreamAudioSource,改**渐进临时文件**——chunk 边到边写 temp 文件,攒 ~64KB 后 `setFilePath` 起播,ExoPlayer 读增长中的文件(经典可靠模式);或用 just_audio 的 `LockCachingAudioSource`。

### 验收(不变)

- 全新段点播放 **≤5s 出声**(后端首 chunk 4.3s 已就位,只欠播放器);缓存段秒播。

## 相关

- 后端实现：`backend/app/services/enrichment/streaming_audio.py`（单次 TTS tee：客户端+落库一次调用）、
  `backend/app/api/v1/endpoints/museums.py` `object_audio_stream`；#269 真流式修复 `tts_service.generate_audio_stream`。
- 前端实现（#262/#265,本 addendum 2 的修复对象）：`catalog_remote_datasource.dart` `getGuideAudioStream` /
  `guide_audio_player.dart` `_loadStreaming` / `tts_chunk_audio_source.dart`。
- 前序交接：`2026-07-06-lazy-tts-streaming-frontend.md`（点播放/409/语速——本交接在其上加流式，不推翻）。
