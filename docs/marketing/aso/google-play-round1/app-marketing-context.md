# GoMuseum · App Marketing Context

生成于 2026-09-08，本轮 ASO 范围：Google Play only，英文 + 法文市场。来源：`docs/play-assets/store-listing/{en-US,fr-FR,app-store-keywords-draft}.md`、`docs/marketing/gomuseum-organic-launch-plan.md`、代码库事实核查（语言选择器、`/chat/ask` 状态）、用户本轮任务书。

## 1. App Overview

- **App Name:** GoMuseum
- **App ID (Apple):** 无——本轮不做 iOS，且尚无 App Store 线上 listing
- **App ID (Google Play):** `com.gomuseum.app`
- **Category:** 待确认（未接触 Play Console，不臆测）
- **Platform:** Android（本轮范围）
- **Price Model:** Freemium — 前5次识别+首个语音讲解免费，之后 Paris City Pass（7天，覆盖4馆无限识别+语音）
- **Launch Date:** 尚未公开发布，当前在内测/封闭测试轨道（`play.google.com/store/apps/details?id=com.gomuseum.app` 对非白名单用户不可访问）
- **Current Version:** 内测中，版本号非本轮 ASO 相关信息，略

## 2. Value Proposition

- **Problem:** 游客站在博物馆展品前，不知道这件作品的背景故事；要么排队租传统语音导览器（押金、固定讲解路线、还要归还），要么现场查通用百科内容，体验割裂、耗时
- **Target Audience:**
  - 英文市场：计划前往或正在巴黎旅行的国际游客
  - 法文市场：法国本地用户及其他法语游客（含本地家庭/学生客流）
- **Unique Differentiator:** 拍照识别眼前任意展品，秒级获得基于真实来源、事实核查过的文字+语音讲解——不受固定路线限制，不需要先知道作品名称。这是 2026-08-26 一轮竞品调研已确认的空位（见下方竞品表）
- **Elevator Pitch (EN):** "Point your camera at any artwork — get an instant, fact-checked audio guide. No rental, no fixed route."
- **Elevator Pitch (FR，待 phase 3 精修):** "Photographiez une œuvre, écoutez son histoire à l'instant — sans location, sans parcours imposé."

## 3. Competitive Landscape

以下是既有认知（来自 2026-08-26 ASO 调研，记录在 `en-US.md`/`fr-FR.md` 开头），**尚未经过本轮 Phase 2 的真实 Google Play 搜索结果验证**，不得假设其仍是当前最重要的直接竞品：

| App | 已知定位 | 已知强项 | 已知弱项/空位 |
|---|---|---|---|
| izi.TRAVEL | 音频导览，300万+下载 | 覆盖广、下载量大 | 选景点听讲解，无拍照识别 |
| Bloomberg Connects | 博物馆官方合作型音频导览 | 官方背书、多馆覆盖 | 无拍照识别，依赖官方合作关系（GoMuseum 明确不做这个定位） |
| GuidiGO | 音频导览 | — | 无拍照识别 |
| Smartify | 艺术品拍照识别 | 定位与 GoMuseum 最接近 | 需 Phase 2 实测覆盖范围、评分、法语市场表现 |

## 4. Current ASO State

- **Title:** GoMuseum（未变体测试）
- **Short description (EN, 69/80字符):** "Scan artwork at the Louvre & Orsay for an instant museum audio guide."
- **Short description (FR):** "Photographiez une œuvre au Louvre ou à Orsay pour un guide audio instantané."
- **Full description:** 已有 EN/FR 两版，见 `docs/play-assets/store-listing/{en-US,fr-FR}.md`
- **Keyword draft (仅 Apple 关键词字段草稿，非本轮范围):** `orsay,orangerie,petitpalais,museum,scan,painting,artwork,recognition,sculpture,audio,tour,exhibit,culture,france`
- **Rating:** 无——尚未公开发布，无法获取
- **Screenshots:** 已有 EN/FR/ZH 三语成套截图（`docs/play-assets/screenshots/`），Feature Graphic 三语已定稿（`docs/play-assets/feature-graphic/`）

## 5. Goals & KPIs

来自 `docs/marketing/gomuseum-organic-launch-plan.md`：

1. **首发 1-2 周内积累安装/评分速度**，卡住"scan/拍照识别"这个当前竞品未占的关键词空位（Google Play 排名算法对新品早期速度敏感）
2. **零广告预算，纯自然渠道**——本轮 ASO 产出的关键词/文案要能独立支撑自然搜索转化，不依赖付费加权
3. **英文+法文两个市场都要独立验证方向A（拍照识别）成立**，而非只在英文市场验证后简单套用法文

## 6. Resources & Constraints

- **Budget:** 0（纯自然渠道，见 [[gomuseum-organic-launch-plan]]）
- **Team:** 个人开发者/小团队
- **Tools:** 无 Appeeky 或其他付费 ASO 关键词数据订阅——本轮关键词研究**没有真实检索量/难度数据来源**，只能用搜索结果数量、自动补全、语义相关性做方向性判断，必须逐项标注
- **Constraints:**
  - App 尚未公开发布，无法做"线上 listing 审计"，只能做 Pre-launch Draft Audit
  - 无法连接 Google Play Console
  - 预设问答（AI生成、随内容返回）是真实功能；自由提问/实时AI对话（`/chat/ask`）已下线，返回503，**任何文案不得暗示后者**

## 7. Markets

- **Primary:** 英文（国际游客，法国境内使用场景为主）
- **Secondary（本轮同等优先级）:** 法文（法国本地 + 法语游客）
- **本轮不覆盖:** 中文及其余7种产品语言的 ASO 方案（商店 listing 本身三语已配好并保持上架，不受影响）
- **Languages (product):** 10种，含简体中文与繁体中文两个独立选项（`kSupportedLocales`，代码已核实）

## 关键发现与下一步

- **强项可用:** 拍照识别定位已有初步竞品空位证据、EN/FR 商店文案已有一稿基础、视觉素材（截图/Feature Graphic）已备齐
- **明显缺口:** 竞品结论未经本轮验证、关键词无真实检索数据源、"预设问答 vs 实时对话"的边界必须在所有文案里守住
- **下一步:** Phase 1 剩余两个技能 → `android-aso`（核实 Play 规则/字符限制）、`aso-audit`（Pre-launch Draft Audit）
