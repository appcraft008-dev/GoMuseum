# GoMuseum · App Marketing Context

**本轮：Google Play ASO Round 1（重做版）· EN + FR · 检索日 2026-09-21**
取代 2026-09-19 首版。首版的产品事实来自项目文档转述，本版全部改为**实测**（prod DB / prod API / Google Play 实访），并因此推翻了首版三条结论。

---

## 1. App Overview

| 项 | 值 | 来源 |
|---|---|---|
| App Name | GoMuseum | — |
| Google Play package | `com.gomuseum.app` | `deployment/website/index.html` CTA 链接 |
| 线上 listing | **不存在**。`play.google.com/store/apps/details?id=com.gomuseum.app` → **HTTP 404**（2026-09-21 实测） | WebFetch |
| Console 状态 | v39 在内测轨道，未推正式轨道 | 项目记录 |
| Category | Travel & Local（建议，见 `current-listing-audit.md`） | — |
| Price Model | Freemium：免费额度 + 一次性 City Pass（非订阅） | — |
| 本轮平台 | **仅 Google Play**。不涉 Apple。 | brief §二 |

---

## 2. Value Proposition

- **Problem**：游客站在一幅画前，**不知道它叫什么**。展签是法语且信息极少，很多作品墙上根本没有编号 —— 于是租来的语音导览（要输编号）和手机搜索（要知道名字）**都用不了**。
- **Target Audience**：EN = 计划前往/正在巴黎的国际游客；FR = 法国本地用户及法语游客。
- **Unique Differentiator**：拍照识别**取代"先查到它是什么"这一步**。不是"多一个功能"，是把一个必经步骤删掉。
- **Elevator Pitch**：你不需要知道它叫什么，拍一下就能听它的故事。

> ⚠️ 这条痛点**不是我们假设的**，有竞品用户原话佐证，见 `competitor-analysis-en-fr.md` F5。

---

## 3. 产品真实能力（2026-09-21 实测，**本版最重要的修正**）

### 3.1 藏品与讲解覆盖

prod DB 直查（`object_content_sections` JOIN `museum_objects` JOIN `museums`，`status='published'`）：

| 馆 | 目录藏品 | 可浏览(有图) | **有讲解 EN** | **有讲解 FR** | **有音频 EN** | **有音频 FR** |
|---|---|---|---|---|---|---|
| Louvre | 17,283 | 10,367 | 327 | 322 | 201 | 201 |
| Orsay | 6,789 | 2,061 | 273 | 269 | 3 | 1 |
| Petit Palais | 3,009 | 1,663 | 47 | 47 | 0 | 0 |
| Orangerie | 140 | 15 | 18 | 18 | 15 | 15 |
| **合计** | **27,221** | **14,106** | **665** | **656** | **219** | **217** |

`content_status` 分布：**ready 665 / stub 26,556**（2.4%）。

**其余 8 种语言**：文字讲解与 FR 同量级（各语 656 左右，全 10 语齐整）；**音频各语仅约 36 件**（Louvre 20 + Orangerie 15 + Orsay ~1）。

### 3.2 这对文案的硬约束

1. 🔴 **"thousands of works" / "des milliers d'œuvres" 是失实表述，必须删**。首版 `metadata-final-*` 和 `docs/play-assets/store-listing/*.md` 里都有这句。真实可用数是 **650+ 件文字讲解 / 200+ 件音频（EN）**。这不是保守问题，是 Play「功能与覆盖必须属实」的政策风险。
2. 🔴 **"10 种语言"只能挂在文字讲解上，不能挂在音频上**。首版把它放进 `SCAN & LISTEN` 区块紧跟音频条目，读起来像"10 语音频"，而真实是各语约 36 件。
3. 🟡 **扫到 stub 件（26,556 件，占 97.6%）的真实体验**：`maybe_trigger` 只在**后台**懒生成，且有全局日上限 300 段。站在画前的用户**当场拿不到讲解**，看到的是「待完善」。所以任何"scan anything → instantly hear its story"的表述都过头了。诚实且仍然有力的写法：**识别永远给得出身份（标题/作者/年代/材质，来自馆藏目录），深度讲解覆盖 650+ 件**。

### 3.3 其它既有约束（沿用，未变）

- 预设问答：仅预生成的常见问答，**不支持自由输入、不支持实时对话**（`/chat/ask` 503）。不得用 "Ask AI anything" 类表述。不进标题/简短描述/前三张截图。
- 不得暗示与任何博物馆存在官方关系。
- **全篇不拿 "AI" 字样当卖点**（2026-09-13 用户拍板）。本轮实测为这条决定找到了外部证据，见 `competitor-analysis-en-fr.md` F6。
- 🔴 **新增风险（本轮发现）**：GoMuseum 识别是**服务端调用**，音频从 R2 流式取 —— **全程依赖网络**。而两个不同竞品的用户各自抱怨"卢浮宫里网络极差"，竞品普遍把 offline 当头部卖点。详见 F7。

---

## 4. 竞争格局（一句话版，详见 competitor-analysis-en-fr.md）

- **EN `louvre guide`**：无任何识别类玩家，在位者评分 2.9–3.7，可攻。
- **EN `art recognition` / `scan painting identify`**：**拥挤**，但多数是**艺术品估值**意图（Art Appraisal: Scan & Value 等），非看展意图。空位不是"没人占"，是"被占错了"。
- **FR `reconnaissance œuvre d'art`**：**Smartify 4,6★ 排第 1**，识别角度在法语市场**已有强在位者**。
- **FR `audioguide louvre`**：仅 8 个结果，头部 2,5★/2,0★，**这才是法语市场的空位**。

→ **EN 与 FR 的机会结构相反**，这是本轮最具操作性的发现。

---

## 5. Goals & KPIs（本轮范围内）

1. 商店页转化率（Store Listing CVR）—— 主指标
2. 首次成功识别率 / 安装后首次识别耗时 —— 质量闸，防"低质量增长"
3. 识别成功后播放讲解比例 —— 验证 scan→listen 链路成立

详见 `experiment-and-measurement-plan.md`。

## 6. Resources & Constraints

- 预算：**零广告预算**，纯自然渠道（`docs/marketing/gomuseum-organic-launch-plan.md`）
- 团队：单人
- 约束：零真实用户 ⇒ 无任何自有转化/排名基线，所有 A/B 必须等有流量后才能跑

## 7. Markets

- 本轮：en-US（主）、fr-FR（主）
- 产品支持 10 语；zh-CN listing 已配好保持上架，但本轮不做其 ASO
