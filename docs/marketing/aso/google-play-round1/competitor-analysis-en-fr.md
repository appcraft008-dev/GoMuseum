# GoMuseum · Competitor Analysis — EN + FR (Google Play)

**数据来源：Google Play 网页版实访（Chrome），en_US/gl=US 与 fr_FR/gl=FR 两套区域参数分别检索。检索日 2026-09-21。**
所有排名、评分、评论数、下载量、描述原文均为页面实际显示值。**无任何搜索量/难度数据** —— Play 不公开，本轮也未购买第三方数据源。凡涉及"竞争程度"的判断，依据是结果数量、在位者评分与评论量，属**方向性判断**。

---

## F1–F7：七项实测发现（按对决策的影响排序）

### 🔴 F1. 「拍照识别是无人占领的空位」——**在英文关键词层面不成立**

`scan painting identify`（en_US）返回**至少 10 个艺术品识别 App**：

| App | 开发者 | 评分 |
|---|---|---|
| Painting Recognition - ArtScan | Hanva,LLC | 2.0 |
| Art Scanner with AI | Loyd Kim | 3.9 |
| Artident: Art Identification | Seapps | — |
| Art Appraisal: Scan & Value | EternalBeam Software | 4.1 |
| Painting Identifier | Asil ARSLAN | 2.9 |
| Artora: Art Scan & Identifier | Scaling Engine Limited | 4.5 |
| Artwork Identifier | Asil ARSLAN | 3.0 |
| The Eye: Painting Identifier | NerdForm Labs LLC | — |
| ArtScan – Discover Art | SashaSer | — |
| Art Identifier & Value | Three Minds Hub | 4.0 |

`art recognition`（en_US）头部：Google Arts & Culture 4.2 / ArtScan 2.0 / Art Scanner with AI 3.9 / Artly 4.5 / **Smartify 4.6**。

**但关键在于意图分层**。这批 App 里名字带 **Value / Appraisal / Identifier** 的一大半服务的是**"我家这幅画值多少钱"**，不是"我站在卢浮宫里这是什么"。

> **修正后的结论**：识别这个**功能词**空间是拥挤的，但**"博物馆现场识别"这个意图**没有被卢浮宫场景的玩家占据 —— `louvre guide` 的结果里**一个识别类 App 都没有**。
> **对既有资料的修正**：`docs/play-assets/store-listing/en-US.md` 开头写的"none of them do photo recognition… largely unclaimed"**不准确**，应改为"没有任何一个巴黎博物馆导览 App 做现场识别"。

### 🔴 F2. 「audio guide 是 izi.TRAVEL 垄断的红海」——**不成立**

`museum audio guide`（en_US）**只返回 8 个结果**：

British Museum Audio（官方，4.6）/ Acropolis Museum - Audio Guide / Museum Audio Guide (OBVA) / VoiceMap 4.7 / **Louvre Museum Free Guide 2.9** / Egyptian Museum Audio Guide $3.99 / British Museum 3D Audio Guide / PocketGuide 3.9。

**izi.TRAVEL 没有出现。Bloomberg Connects 没有出现。GuidiGO 没有出现。**

> **对既有资料的修正**：既有稿称此类目被 izi.TRAVEL（300 万+下载）等"saturated"，**Play 当前搜索结果不支持这一说法**。这个词反而是**薄的**。
> ⚠️ 不推翻"这些 App 存在且体量大"这一事实 —— 只推翻"它们占据了这个搜索词"。

### 🔴 F3. `louvre guide` 在位者**评分普遍很低**，是可攻的

`louvre guide`（en_US）结果序：

| # | App | 开发者 | 评分 | 是否识别 | 是否固定路线 |
|---|---|---|---|---|---|
| 1 | Louvre Visit, Tours & Guide | TourBlink | 3.7 | ✗ | ✓ 60–120 分钟路线 |
| 2 | Louvre Museum Free Guide | MUSEUM BUDDY | **2.9** | ✗ | ✓ 离线路线 |
| 3 | Louvre Museum Travel Guide | Tours & Travel Inc. | — | ✗ | ✓ |
| 4 | Louvre Chatbot Guide | Emoji Guide | 3.6 | ✗ | 聊天机器人 |
| 5 | Louvre in 2 Hours | In 2 Hours | — | ✗ | ✓ |
| 6 | **TourLens: Louvre Guide** | Fleek Inc. | — | ？名字暗示镜头 | ？ |
| 7 | Louvre Museum Audio & Map Tour | Heritage & Lexicon | — | ✗ | ✓ |

同家 MUSEUM BUDDY 的 **Orsay Museum Free Guide 仅 1.6★**（en）/ **2,0★**（fr）。

> ✅ **已查清（2026-09-21）**：`TourLens: Louvre Guide` **确实做扫描识别**，标语就是 "Scan Anything to Listen"。但它是**已弃的项目**，不构成防守障碍 —— 详见下方档案。
> ⭐ **它零评分、1K 下载还能排 `louvre guide` 第 6，这是"这个词防守有多弱"的最佳单点证据。**

### 🔴 F4. **EN 与 FR 的机会结构相反** —— 本轮最具操作性的发现

| 查询 | 市场 | 结果数/强度 | 头部在位者 |
|---|---|---|---|
| `art recognition` | EN | 拥挤但意图错位 | Google Arts & Culture 4.2、Smartify 4.6（第 5） |
| `louvre guide` | EN | **弱**，无识别玩家 | TourBlink 3.7、MUSEUM BUDDY 2.9 |
| `reconnaissance œuvre d'art` | **FR** | **Smartify 排第 1，4,6★** | Smartify / ArtScan / Artly 4,5 / DailyArt 4,7 / Google A&C |
| `audioguide louvre` | **FR** | **仅 8 个结果，头部很弱** | MUSEUM BUDDY 2,5 / Louvre Chatbot 4,5 / TourBlink 4,3 |
| `guide musée paris` | FR | 拥挤，但被**城市指南**和 Paris Musées 官方 App 占据 | Odyssey 4,2 / Civitatis 4,7 / Paris Musées Second Canvas 4,4 |

**含义**：
- **EN**：识别角度在卢浮宫语境下无人占 → 方向A（scan）可用作差异化，但**搜索获客**要靠 `louvre guide` 类专名词。
- **FR**：识别角度**已被 Smartify 以 4,6★ 占住**，硬碰是劣势；而 `audioguide louvre` 是真空位 → **法语市场应以 audioguide/guide 词做获客，scan 退为页面转化卖点**。

这正好回答 brief §五要求的"判断方向A在英文和法文市场是否同样成立"：**不同样成立**，且有证据。

### 🟢 F5. **核心痛点被竞品用户原话证实**（本轮最强的一条证据）

MUSEUM BUDDY「Louvre Museum Free Guide」2026-06-06 差评，用户原话大意：买了 premium 仍被要求升级才能看地图，而且**馆里很少有作品标着馆藏号，没有 App 里的地图就没法手动找到它们**。

> 这不是我们的营销假设，是一个真实付费用户自己描述的**识别断点**：墙上没有编号 ⇒ 传统导览的"输编号听讲解"模型在卢浮宫现场直接失效。
> **GoMuseum 的相机识别恰好消掉这一步。** 这条应当成为整个 ASO 叙事的锚点。

### 🟢 F6. **"AI" 被用户当作差评词** —— 2026-09-13 那条决定有了外部证据

TourBlink 2025-09-18 差评，用户原话包含："Poor grammar, incorrect facts, and an AI voice (and probably AI writing)"，并称 Wikipedia 更有信息量。

> 用户 2026-09-13 拍板"全篇不拿 AI 当卖点"时给的理由是"AI 已同质化、反而招来对内容质量的警惕"。**本轮实测证实了后半句**：在这个类目里，"像 AI 写的"已经是差评理由本身。
> **推论**：GoMuseum 的 "grounded / fact-checked / never invented" 不只是一个卖点，它是**针对这条已成形的用户疑虑的直接反驳**，应当前置。

### 🔴 F7. **新增风险：GoMuseum 全程依赖网络，而卢浮宫网络很差**

两个不同 App 的用户独立抱怨：
- MUSEUM BUDDY 2026-05-27：在馆内 4.5 小时，连馆方 WiFi 也下不完内容，卡在 68%。
- TourBlink 2025-09-18：没有网络连引导功能都用不了，**"internet access at the Louvre is terrible"**。

竞品普遍把 **OFFLINE** 当头部卖点（TourBlink 整段 `OFFLINE APPLICATION`；MUSEUM BUDDY 强调 "fully offline audio guide"）。

> **GoMuseum 识别是服务端调用、音频从 R2 流式取 —— 现场没网就全废。**
> 这是 ASO 修不了的产品风险，且它**反噬"即时"这个卖点**。本轮处理：文案不承诺 offline、不夸"instant"，并把它列入 `executive-summary.md` 的产品侧待办。**不建议在没有离线能力前把 offline 写进任何素材。**

---

## 主要竞品逐个档案

### Smartify: Arts and Culture — `com.mobgen.smartify`

| 项 | 值（en_US，2026-09-21 页面显示） |
|---|---|
| 标题 | Smartify: Arts and Culture |
| 开发者 | Smartify CiC |
| 评分/评论 | **4.6★ / 7.92K reviews**（评分区块显示 4.7 / 7.71K） |
| 下载量 | **1M+** |
| 更新 | 2026-09-16（活跃维护） |
| 类目 | Education |
| 收费 | In-app purchases |
| 简短标语 | Discover Art, Explore Museums |
| 识别 | ✓ "Scan paintings, sculptures and objects to reveal what you're looking at" |
| 自由探索 | ✓ |
| 固定路线 | 部分（audio tours） |
| 多语言 | ✓ |

**核心定位**：全球广度 —— "Hundreds of museums, art galleries, historic places and more, all in one app"，社会企业，与馆方合作分成。

**它自己的免责声明（重要）**：描述末尾明确写着与馆方合作是为保护艺术家版权，并说明**无法识别每一件作品**。
> ⭐ 这是一个**行业先例**：类目里最成功的识别类 App 自己就在商店描述里限定识别覆盖。GoMuseum 按 F1/3.2 诚实标注覆盖量，**不是竞争劣势，是这个类目的通行做法**。

**差评主题**（页面显示的高赞评论）：
1. **强制注册挡死使用**（2023-09，44 人认为有用）：注册表单姓名字段报错，无法继续，直接卸载。官方回复承诺加 SKIP 按钮。
2. **识别失败/体验差**（2023-06，37 人认为有用）：为识别一幅画而下载，扫描框固定为正方形不可调，缩放只有两档，点扫描后卡住数分钟，多次重试无果。官方回复指出有"Continue as a guest"入口。
3. **识别覆盖不全**（2021-03，67 人认为有用）：整体好评，但明说"它不能识别所有东西"。

**GoMuseum 可利用的差异化**：
- 🎯 **免注册即用**：Smartify 最高赞差评就是注册墙挡住了使用（而且官方回复说"其实有游客入口"= 入口没做明显）。GoMuseum 的 guest 模式应当**前置到截图里**，不是埋在功能列表。
- 🎯 **四馆深度 vs 全球广度**：Smartify 是合作制、覆盖广但每馆浅；GoMuseum 是四馆深挖。定位不冲突，可共存。
- ⚠️ **不要在 FR 市场正面打识别**（见 F4）。

### Louvre Visit, Tours & Guide（TourBlink）— `com.tourblink.louvre`

| 项 | 值 |
|---|---|
| 评分/评论 | 3.7★ / 1.01K reviews |
| 下载量 | 100K+ |
| 更新 | 2026-08-15 |
| 类目 | Travel & Local |
| 收费 | In-app purchases，路线单价"不到 €5" |
| 识别 | ✗ |
| 固定路线 | ✓ 核心卖点，60–120 分钟 itineraries |
| 离线 | ✓ 整段 `OFFLINE APPLICATION` 头部卖点 |
| FR 本地化 | ✓ 标题译为「Louvre : visite et guide」，FR 评分 4,3 > EN 3.7 |

**差评主题**：① 已购买但播放三件后被要求再次付费（IAP 解锁失败）；② 语法差、**事实有误**、AI 配音、房间号与顺序不对、无网不能用。

> 💡 **可直接借鉴的一点**：TourBlink 在 FR 把标题本地化了，FR 评分明显高于 EN。**GoMuseum 的 FR 标题必须是原生法语，不是英文标题照搬** —— 这与 brief §三的要求一致，并有实例支持。

### Louvre Museum Free Guide（MUSEUM BUDDY）— `air.com.lvr.paris.vusiem`

| 项 | 值 |
|---|---|
| 评分/评论 | **2.9★ / 246 reviews**（评分区块 2.8 / 231） |
| 下载量 | 50K+ |
| 更新 | 2026-09-18 |
| 收费 | In-app purchases |
| 识别 | ✗ |
| 固定路线 | ✓ |
| 离线 | ✓ 头部卖点，"audio for over a thousand highlights" |

**同系列**：Orsay（1.6★ en / 2,0★ fr）、Vatican、Rodin、Egyptian、Pitti、Accademia —— 一个单馆导览 App 矩阵，**评分普遍很低**。

**差评主题**（全部是 2026 年的近期评论）：① 付费后引导选项消失；② **馆内下载不完**（4.5 小时卡 68%）；③ 付费后仍被要求升级 + **墙上没有馆藏号导致找不到作品**（= F5）。

> 这是 GoMuseum 最直接的"被攻击目标"：同样打 `louvre guide` 高意图词，在位者 2.9★ 且差评集中在**离线下载模型本身的失败**和**编号找不到**。

### Louvre Chatbot Guide（Emoji Guide）— `com.wavemining.louvre`

FR 4,5★ / EN 3.6★。自我描述为 "free, **unofficial** chatbot guide"。

> 两点可借鉴：① 它**主动写明 unofficial** —— 与本项目"不得暗示官方关系"的要求是同一做法，说明这在类目里是常规且不伤转化；② 它在 FR 的评分显著高于 EN，再次印证法语市场对本地化内容的回报。

### ⭐ TourLens: Louvre Guide（Fleek Inc.）— `com.fleek.wuzu`

**GoMuseum 唯一的正面同类：同样是"在卢浮宫扫作品听讲解"。** 2026-09-21 详情页实测。

| 项 | 值 |
|---|---|
| 评分/评论 | **无评分、无评论**（页面不显示星级） |
| 下载量 | **1K+**（四个量级低于 Smartify） |
| 更新 | **2024-09-24 —— 两年未更新** |
| 可用性 | 页面显示 "This app is not available for any of your devices" |
| 收费 | **完全免费，无内购** |
| 开发者 | (주)플릭 / Fleek Inc.，首尔江南区；客服邮箱 `busking@fleek.fitness`（健身域名） |
| 类目 | Travel & Local |
| 内容分级 | Teen · "Diverse Content: Discretion Advised"（对博物馆 App 而言异常） |
| 标语 | **"Scan Anything to Listen"** |

**定位漂移（它失败的原因，也是我们的机会）**：正文描述讲的是"扫一切"——绘画、雕塑、建筑、地标、街道、自家社区；只有 What's New 才改口讲卢浮宫的 docent 式讲解。这是一个**泛用识别 App 硬转到卢浮宫场景**，没有任何一馆的内容深度。

**对 GoMuseum 的三点含义**：
1. 🔴 **"零竞争"的说法必须收回**。正面同类存在，且排在 `louvre guide` 第 6。
2. 🟢 **但它不构成防守障碍**：Play 排名重安装量、互动、评分、更新近度 —— 它四项全弱，两年未更新且在部分设备不可用。
3. ⭐ **它同时验证了机会和失败模式**：有人看到了同一个空位（说明判断没错），但"扫一切"的泛用定位没有内容深度支撑，做不起来。**GoMuseum 的差异化恰恰是四馆深度（665 件讲解 / 219 件音频），不是"能扫更多东西"。** 这条应当写进定位纪律：**别往"扫一切"的方向漂。**

### Bloomberg Connects — `org.bloomberg.connects.docent`

本轮**未能取得页面数据**（详情页未访问）。既有资料称其已拿下 Paris Musées 官方合作 —— **本轮未验证**。但 FR `guide musée paris` 结果里确实有多个 **Paris Musées 自有 App**（Musée d'Art moderne 3,3 / Musée Libération / Paris Musées Second Canvas 4,4），官方阵营在法语市场确实存在。
> ⚠️ 小皇宫（Petit Palais）属 Paris Musées 体系 —— GoMuseum 覆盖该馆时，**撇清官方关系的声明尤其必要**。

---

## 竞争位置小结

```
                        识别能力强
                             │
              Smartify ●     │
            (全球广·馆方合作) │      ● GoMuseum（目标位）
                             │        四馆深 · 免注册 · 接地讲解
   全球广度 ─────────────────┼───────────────── 单馆/单城深度
                             │
                             │   ● TourBlink 3.7
              Bloomberg?     │   ● MUSEUM BUDDY 2.9（离线路线，评分差）
                             │   ● Louvre Chatbot 3.6/4.5
                        无识别能力
```

## Top Opportunities

1. **Quick Win**：`louvre guide` 在位者评分 2.9–3.7，且差评集中在"付费失败"和"找不到作品"。GoMuseum 的免注册 + 免费额度 + 相机识别对这三条各有一记。
2. **Keyword Gap（EN）**：`louvre` × `scan` 的组合**零竞争** —— 没有任何巴黎博物馆 App 做识别。
3. **Keyword Gap（FR）**：`audioguide louvre` 仅 8 个结果且头部弱 —— 比识别词好打得多。
4. **Creative Edge**：F5 那条用户原话可以直接翻译成 Slot 1 的文案角度（"墙上没有编号也没关系"）。
5. **Trust Edge**：F6 说明"不脑补、有据可溯"在这个类目是**有需求的反命题**，不是自说自话。

## Threats to Monitor

- **`TourLens: Louvre Guide`（Fleek Inc.）** —— 名字暗示镜头识别且已排 `louvre guide` 第 6。**上传前必查**。
- **Smartify 在 FR 的统治力**（`reconnaissance œuvre d'art` 第 1，4,6★，1M+ 下载，两周一更新）。
- **Paris Musées 官方 App 矩阵**在法语市场的存在，叠加小皇宫的归属关系。
- GoMuseum 自身的**网络依赖**（F7）—— 这是竞品的成熟卖点而我们没有。

## 法语差评实读（2026-09-25，待办第 3 项）

**为什么做**：上文法语文案的痛点是从**英文**评论推的（只读过英文页）。这次直接读法语商店（`lang=fr country=fr`）的评论。
**方法与样本**（⚠️ 小样本，主题计数是关键词粗计、类别有重叠，只表示量级）：`google-play-scraper`（非官方）取最新评论，Sort=NEWEST：TourBlink 53 条、MUSEUM BUDDY 11 条、Louvre Chatbot 93 条、Smartify 156 条，共 313 条。**评论时间跨度很大**：TourBlink/MUSEUM BUDDY 的差评大多是 2016–2020 年，产品可能已变；2024–2026 年的近期差评单独标出。评论 ≠ 搜索需求，也不是随机样本（人们更爱在极端体验后留评）。

### 各家读到了什么

| App（FR） | ≤3★ 主题（条数/该档总数） | 好评主题 |
|---|---|---|
| **TourBlink**（4,3★） | **付费不满 8/14**（"Tout est payant"、"on a déjà payé notre ticket"、"autant prendre celui du musée"、多收 3 € 票务费）；**AI/机器人语音 3/14**；**内容不准/过时 3/14**；缺路线 2/14 | 路线（"sans se perdre dans ce labyrinthe"）：提到路线的 11 条里 8 条是 4–5★ |
| **MUSEUM BUDDY**（2,5★，仅 11 条） | **付费/升级 5/7**（"dites gratuite mais demande sans cesse un accès à votre carte bancaire"）；无法语 3/7 | 几乎没有 |
| **Louvre Chatbot**（4,5★） | 只有 10 件作品（2019）；"on ne peut pas poser nos questions"（**2025-12**）；错别字；讲得太浅 | **轶事/背景故事**、适合和孩子一起、"Plus d'œuvres serait idéal"（多条） |
| **Smartify**（FR 识别词第 1） | ≤2★ 共 64 条：**识别失败 ~26**（"Ne reconnaît pas la Joconde"、"1 tableau sur 10"、"seulement les connus"、"ne reconnaît pas les photos, seulement des scans"）；**崩溃/打不开 ~19**；**全英文/没有法语 ~6**（"le texte en anglais qui est juste à côté du tableau"）；强制注册 2 | — |

### 结论（对 GoMuseum 的含义）

1. **⭐ 最近期的法语差评是"机器人语音 + 内容有错"**（TourBlink 2024-10、2025-02：voix robotique / informations fausses / "tirées d'une IA ou de wikipédia"；2020 还有 4★ 说法语声音"métallique"）。GoMuseum 的音频也是合成语音。⇒ **法语文案与截图不得暗示真人/自然人声**（现有 FR 稿没有这类表述，已核对）；法语音频的第一印象是真实风险，值得用真人耳朵对照这条差评检查一次（**这是需要你判断的事**，我不评音质）。"SOURCED, NEVER INVENTED / SOURCÉ, JAMAIS INVENTÉ"那一屏直接对应"信息有错"的抱怨。
2. **⭐ 付费不透明是法语差评里最集中的一条**（TourBlink 8/14、MUSEUM BUDDY 5/7；抱怨的是"标着免费却处处收钱/已买门票还要再付"，不是价格本身）。⇒ 现有 FR 完整描述已写明"5 premières reconnaissances et premier guide audio gratuits"和"Un paiement unique, pas un abonnement"，方向对；**应用内付费墙同样要在点击前就说清什么免费、什么收费**（记下，不在本轮范围）。
3. **Smartify 的法语用户主要被"识别不出来"和"全是英文"伤到。** 后者是 GoMuseum 的真实差异（原生法语讲解，此前只是推断，现在有法语原话佐证）；前者是**警告**：扫描优先的产品最容易吃 1★，而 GoMuseum 的识别边界是有图作品（14,106/27,221）。**"识别失败时的体验"决定评分，值得单独审一遍**（未做）。
4. **"提供更多作品"是好评产品也在被要求的东西**（Louvre Chatbot 4,5★ 仍有多条"plus d'œuvres"）。覆盖量是 GoMuseum 相对它的现实优势，页面/描述可以在不夸大的前提下强调。
5. **家庭/带孩子**的提及有 10/313 条（TourBlink "idéal quand on a un enfant qui n'aime pas les musées"、Chatbot "jeu d'énigmes en famille"）。**只是假设，不是结论**：样本小，且没有证据说明 GoMuseum 更适合孩子。不建议据此改文案。
6. **路线是有人要的**（TourBlink 好评里 8 条提路线）。GoMuseum 选择"自由探索、不做寻路"，这意味着**想要固定路线的那批人不是我们的目标用户**，别为他们改定位；但也说明"EXPLORE FREELY"的对面确实存在一个受欢迎的选项。
7. **没找到的**：**网络/离线的抱怨在 313 条法语评论里为 0**（英文评论里有 "internet at the Louvre is terrible"）。这**不能**推出法语用户不在意网络（样本小、多为老评论），只说明**法语侧没有证据支持把"离线"当作痛点写进法语文案**，此前 F7 只能作为英文侧证据。

### 对既有文案的影响
**无需修改已送审文案。** 上面第 1、2 条与现有法语稿一致；第 3 点的"原生法语"目前只体现为描述里"10 种语言：français…"一行，**没有被单独强调**（可在下次改描述时考虑，放量后再定）；其余是产品/后续待办，不属 listing。
