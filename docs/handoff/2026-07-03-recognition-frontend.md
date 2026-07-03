# 交接（前端）：拍照识别流程（三档 UI + 引导拍签）

> 后端已先行：`POST /api/v1/museums/{slug}/recognize` 已上 staging（接地识别,契约§识别）。
> 老 `/recognition` 端点已 deprecated——新识别流程一律走新端点。

## 端点

`POST /api/v1/museums/{slug}/recognize`
- multipart 字段 `image`（拍摄的 JPEG）；query：`language`（App 当前语言码）、`mode`（默认 `artwork`；引导补拍墙签时传 `label`）
- 同一张照片重复提交后端有缓存（秒回）

## 响应与三档 UI

```json
{ "outcome": "match | candidates | unrecognized",
  "match": {"qid","title","artist","thumbnail","confidence"},
  "candidates": [{"qid","title","artist","thumbnail","score"}],
  "label_text": "识别到的墙签文字或null",
  "reason": "not_in_catalog | low_confidence | no_candidates | null" }
```

| outcome | UI |
|---|---|
| `match` | **直接跳详情页**（qid → 现有 guide 路由;懒生成自动接管,页面按现有"待完善/内容"逻辑渲染） |
| `candidates` | **确认卡**："是这件吗？"列出 1-3 个候选（缩略图+title+artist），点选 → 跳该 qid 详情；都不是 → 走 unrecognized UI |
| `unrecognized` | **未收录卡**（见下） |

`title/artist` 已按 `language` 本地化，直接显示。`outcome/reason` 是机器码，文案走 App l10n。

## 未收录卡（按 reason 微调文案）

- 有 `label_text`：「标签上写着 "…"——我们还没收录它的完整讲解，已记下你的需求 ✅」（后端已自动记需求，无需再调）
- 无 `label_text`：「没认出来这件作品」＋主按钮 **「拍下作品旁的说明牌」**：
  - 按钮下配一句引导：「博物馆的小标牌上有作品名和作者，拍它我们就能认出来」（可配小示意图）
  - 点击 → 相机取景框带提示文案（"对准标签文字，占满画面"）→ 第二张照片以 **`mode=label`** 提交 → 响应同上（命中即跳详情；仍未收录显示带 label_text 的版本）
- 次按钮：「重拍」/「取消」

## 确认卡的价值（实现时别省）

用户点选候选 = 一条"真实照片→确认QID"的标注数据（喂后端二期 CLIP 校准）。P1 先把点选行为本地打点或简单埋点即可（后端聚合接口 P2 提供）；至少保证点选跳转路径畅通。

## staging 测试法

- 从 Wikipedia 保存《世界的起源》图片 → App 内"拍"它（或直接选图上传）→ 应 `match` 直开详情
- 拍一张风景/无关照片 → `unrecognized` + 引导拍签按钮
- 手写一张纸 "Le Chat blanc / Pierre Bonnard" 拍下以 `mode=label` 提交 → 应命中《白猫》
- curl 自测：`curl -F "image=@origin.jpg" "https://staging-api.gomuseum.app/api/v1/museums/orsay/recognize?language=zh"`

## 验收

- 三档各自路径可走通；match 直开详情且懒生成正常接管
- 引导拍签二拍链路（mode=label）畅通
- 未收录不显示任何 AI 猜测的名字（只显示 label_text 原文或诚实文案）——这是产品底线（契约 R1）
- `flutter analyze && flutter test` 绿

## 相关

- 契约：`docs/architecture/museum-api-contract.md` §识别
- 后端 spec：`docs/superpowers/specs/2026-07-03-recognition-design.md`
