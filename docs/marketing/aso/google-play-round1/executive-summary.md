# GoMuseum · Google Play ASO Round 1 — Executive Summary（重做版）

**执行日 2026-09-21 · 平台：仅 Google Play · 市场：en-US + fr-FR**
本版取代 2026-09-19 首版。首版的产品事实与竞争判断来自项目文档转述；**本版全部改为实测**（prod DB 直查 / prod API / Google Play 网页实访），并因此推翻了首版的三条核心结论。

---

## 最重要的 5 项发现

### 🟢 1. 覆盖量不是问题——**问题是我一开始用错了框架**（本条结论已反转）

我先测出 prod `content_status` = **ready 665 / stub 26,556（2.4%）**，据此判定 `thousands of works` 失实、是政策风险。

**这个判定错了。** 项目自己的实测值写在 `pipeline.py` 注释里：**懒生成 TTFC 16–18s → 约 20 秒**，"只有第一个看到这件作品的人要等"；`lazy_audio` 同样全覆盖。

⇒ `ready/stub` 测的是**缓存冷热**，不是用户能不能拿到。扫一件冷的，等约 20 秒就有讲解。**`thousands of works` 描述的是系统能力，覆盖 27,221 件目录，表述成立。**

**⭐ 但这件事换来了本轮最好的一句文案。** 最终处置不是在 650 和 thousands 之间选，而是**把数字整个拿掉、改讲机制**——数字必然过期，机制不会：

> **Not written up yet? Scan it anyway — GoMuseum researches that work and writes its guide on the spot.**

竞品没有一个能说这句话。

**教训**：`ready/stub` 这种字段名天然诱导"有/没有"的二分读法，而在懒生成架构下它们只是"热/冷"。**凡按需生成的系统，覆盖率分母都别按库存算。**

### 🔴 2. 「拍照识别是无人占领的空位」——**不成立**，但真相比原结论更有用

`scan painting identify`（en_US）返回**至少 10 个**艺术品识别 App；FR `reconnaissance œuvre d'art` 里 **Smartify 排第 1（4,6★ / 1M+ 下载）**。

**但**：这批 App 里一大半是**估值**意图（Art Appraisal: Scan & Value、Art Identifier & Value、Estimation Tableau…），不是看展意图。而 `louvre guide` 的结果里**一个识别类 App 都没有**。

> **修正后的可辩护表述**：不是"没人做识别"，是**"没有任何巴黎博物馆导览 App 做现场识别"**。

### 🔴 3. 「audio guide 是 izi.TRAVEL 垄断的红海」——**不成立**

`museum audio guide`（en_US）**只返回 8 个结果**，izi.TRAVEL、Bloomberg Connects、GuidiGO **一个都没出现**。`louvre guide` 的在位者评分是 **2.9 / 3.6 / 3.7**，同家 MUSEUM BUDDY 的 Orsay 版只有 **1.6★**。

这个词不是红海，是**薄且防守薄弱**的。首版据此把 `audio guide` 排除在 Title 外，本轮把 `Guide` 放回了 Title。

### 🔴 4. **EN 与 FR 的机会结构相反** —— 本轮最具操作性的发现

| | EN | FR |
|---|---|---|
| 识别词 | 拥挤但**意图错位**（估值），卢浮宫场景无人占 | **Smartify 4,6★ 占第 1** |
| 导览词 | `louvre guide` 弱，在位者 2.9–3.7 | **`audioguide louvre` 仅 8 结果**，头部 2,5★/2,0★ |
| **Title 差异化词** | **`Scan` 进 Title** | **`scan` 不进 Title，改 `Audioguide`** |
| 识别功能的角色 | 获客 + 转化 | **仅转化** |

brief §五 问"方向A 在法文市场是否同样成立" → **不同样成立**，且有证据。这是本轮唯一一条**有依据地调整了既有定位**的结论。

### 🟢 5. 核心痛点与"不用 AI"的决定，都拿到了外部证据

- **痛点**（F5）：MUSEUM BUDDY 付费用户 2026-06 差评自述——馆里很少有作品标着馆藏号，没有地图就没法手动找到它们。**这正是 GoMuseum 相机识别消除的那一步**，而且是用户自己的话，不是我们的营销假设。
- **不用 "AI"**（F6）：TourBlink 差评原话含 "Poor grammar, incorrect facts, and an AI voice (and probably AI writing)"，并称 Wikipedia 更有信息量。用户 2026-09-13 拍板"全篇不拿 AI 当卖点"时给的理由（招来对 AI 内容质量的警惕）**在这个类目已经是成形的用户疑虑**。
  ⇒ 推论：`grounded / sourced / never invented` 不只是卖点，是**针对既有疑虑的直接反驳**，应当前置到 Slot 3（折叠线以上）。

---

## ASO 要让用户一下记住什么（核心交付）

**不是六条并列卖点** —— 商店页停留 3–6 秒，六条并列等于记住零条。

### 核心（唯一要被记住的一句）

> **你不需要知道它叫什么。** 看到哪件拍哪件，立刻知道它是什么、听它的故事。

所有替代方案都卡在同一个前提上：*你得先知道你在看什么*。导览器要输编号，搜索要知道名字，Smartify 要那件在它的合作目录里。识别不是"多一个功能"，是把这一步整个删掉。

### 三根支柱（依次消解三个拒绝理由）

| | 支柱 | 消解 |
|---|---|---|
| 1 | **信得过** — 有据可溯，不脑补 | "AI 生成的能信吗？" |
| 2 | **不受束缚** — 不租不押金不排队，你走到哪它讲到哪 | "比租讲解器强在哪？" |
| 3 | **零门槛试** — 免注册、免费额度、一次性通票不是订阅 | "要花我多少钱？" |

### 转化层（进页面，不进前三张截图）

四馆 · 10 语文字讲解 · 搜索 · 隐私

> 首版把"一站四馆"和核心定位并排放在同一层，这是它最主要的结构问题。方向B 是功能说明，位置应在 Slot 4。

---

## 英文市场最终推荐

| 字段 | 推荐 | 字符 |
|---|---|---|
| Title | `GoMuseum: Louvre Guide & Scan` | 29/30 |
| Short desc | `Scan art at the Louvre or Orsay — no title or number needed, just listen.` | 73/80 |
| Full desc | 见 `metadata-final-en-US.md` | 2105/4000 |
| Slot 1 | `You don't need to know its name.` | — |

## 法文市场最终推荐

| 字段 | 推荐 | 字符 |
|---|---|---|
| Titre | `GoMuseum : Audioguide Louvre` | 28/30 |
| Desc. courte | `Scannez une œuvre au Louvre ou à Orsay : ni titre ni numéro, écoutez.` | 69/80 |
| Desc. complète | 见 `metadata-final-fr-FR.md` | 2466/4000 |
| Slot 1 | `Pas besoin de connaître son titre.` | — |

## 方向A 是否得到验证

**分市场回答：**

- **EN：部分验证，且需要重新表述。** 原命题"识别无人做"被证伪；可辩护的版本是"没有任何巴黎博物馆导览 App 做现场识别"，这一条实测成立（`louvre guide` 结果零识别玩家）。同时 F5 提供了痛点真实存在的用户原话。⇒ **方向A 作为差异化/转化支点成立；作为搜索获客词不成立**（识别功能词的流量意图错位到估值）。
- **FR：不成立。** Smartify 以 4,6★ 占住识别词。法语应改用 `audioguide` 获客，识别降为转化卖点。

**brief 明令"不得在没有数据的情况下宣称已有结论已被验证"** —— 本轮据此把方向A 拆成了"获客"和"转化"两个问题分别回答，而不是笼统说"验证通过"。

## 需要修正的既有结论

| 出处 | 原结论 | 修正 |
|---|---|---|
| `en-US.md` L22 / `fr-FR.md` L21 | "thousands of works" / "des milliers d'œuvres" | **665 / 656 件**。失实，必改 |
| `en-US.md` L3–6 调研注记 | audio guide 被 izi.TRAVEL 等 saturated | Play 当前搜索**不支持**此说法，该词仅 8 个结果 |
| `en-US.md` L5–6 | "none of them do photo recognition"、识别位"largely unclaimed" | 识别类 App 至少 10 个；应改为"无巴黎博物馆导览 App 做现场识别" |
| 首版 metadata（EN） | Title `GoMuseum: Scan Louvre Art` | 改 `GoMuseum: Louvre Guide & Scan`（把 `Guide` 词根放回） |
| 首版 metadata（FR） | 与 EN 同构，scan 优先 | 改 `Audioguide` 优先（F4） |
| 首版 `app-marketing-context` | "9 种语言"已修为 10 | ✅ 保持，但**须限定为文字讲解** |

> ⚠️ 前 3 条所在的 `docs/play-assets/store-listing/*.md` 是 brief §十三 指定的**只读输入，本轮未改动**。修正落在本目录的 metadata 文件里。是否回改源文件请用户定。

## 可以立即实施

1. 用本轮 metadata 替换 Play Console 里的 EN/FR 三个字段（Title / Short / Full）。
2. 按 `creative-brief-en-fr.md` 的顺序与文案重排 8 张截图 —— **素材已齐备，不用重截**。
3. 类目建议 Travel & Local（与 TourBlink / MUSEUM BUDDY 一致；Smartify 选 Education）。

## 仍需真实数据验证的假设

1. **所有关键词判断**。本轮只看到供给侧（结果数、在位者评分），**看不到需求侧搜索量**。Play Console 的 Search terms 报告是唯一能证伪它们的数据源。
2. **`audioguide louvre` 只有 8 个结果** —— 可能意味着供给少（机会），也可能意味着需求少（陷阱）。本轮无法区分，**这是法语方案最大的未知数**。
3. ~~`TourLens: Louvre Guide` 是否真做识别~~ → ✅ **已查清**：确实做（标语 "Scan Anything to Listen"），故 **"零竞争"的说法收回**；但它 1K 下载、零评分、两年未更新，不构成障碍，Title 推荐不变。详见 `competitor-analysis-en-fr.md`。
4. Bloomberg Connects 与 Paris Musées 的官方合作（既有资料的说法）本轮**未验证**。

## 🔴 产品侧风险（ASO 修不了，本轮新发现）

**GoMuseum 全程依赖网络**（识别是服务端调用、音频从 R2 流式取），而**两个不同竞品的用户各自抱怨卢浮宫馆内网络极差**，竞品普遍把 offline 当头部卖点。

本轮处置：文案不承诺 offline、不夸 instant，并在 Full description 末尾加联网提示以管理预期、防 1 星差评。
**但这是产品缺口，不是文案缺口。** 建议列入 backlog 评估。

## 推荐的下一步行动顺序

1. **用户审核本轮文案**（brief §十四 要求所有产出先交审核）
2. 核实 `TourLens: Louvre Guide` 是否做识别 → 决定 EN Title 是否回退到备选 A
3. 决定是否回改 `docs/play-assets/store-listing/*.md` 里那句失实表述
4. 正式轨道放量 → 上传 metadata + 截图 → 部署落地页
5. 累积 ≥1,000 页面访问后启动第一轮 A/B（**不要放量当天就开**）
6. 第 7 天读 Search terms 报告，回填两份 keyword-research 的"仍需验证"章节

---

## 本轮执行边界确认（brief §十四）

✅ 未修改应用代码 · ✅ 未修改 4 个前置输入文件 · ✅ 未连接 Play Console · ✅ 未上传任何素材 · ✅ 未发布任何内容 · ✅ 未做 Apple 相关工作 · ✅ prod 仅只读查询（`SELECT`），无任何写操作
