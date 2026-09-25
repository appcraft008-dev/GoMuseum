# GoMuseum · Keyword Research — en-US (Google Play)

> **当前无真实搜索量/难度数据，以下判断基于搜索结果数量、竞品覆盖、在位者评分与语义相关性，属于方向性判断。**
> 数据来源：Google Play 网页搜索实访（`hl=en_US&gl=US`），检索日 **2026-09-21**。Play 不公开搜索量；本轮未采购第三方数据源，**不虚构任何量化指标**。
> 下表的 Volume / Difficulty 列**不是搜索量与难度数值**，是基于实测证据的**三档定性标注**（高/中/低），并注明证据。

## 证据口径说明

| 我观察到的 | 我能推出的 | 我**不能**推出的 |
|---|---|---|
| 某词返回 8 个结果 vs 30 个结果 | 该词的**供给侧**竞争强度 | 该词的需求侧搜索量 |
| 在位者评分 2.9 / 评论 246 | 在位者**质量弱、可攻** | 排名难度数值 |
| Play 结果里出现/不出现某 App | 该 App 是否占据该词 | 它的下载量归因 |

---

## ⭐ 排除一个关键词，只有三种正当理由（2026-09-21 补写）

用户提出的质疑：**"有竞品用了的词我们就不能用了吗？高频词不用，用户不就搜不到我们了？"**
**这个质疑是对的，本文件首版没把三种理由分开写，读起来像"竞品占了就得躲"。** 现补上判据：

| 类型 | 判据 | 结果 | 本文件里的例子 |
|---|---|---|---|
| **① 失实** | 说了就是假话 | **完全不用**，任何字段都不用 | `offline`（产品不支持）、`thousands of works` |
| **② 意图错配** | 能排上去，但搜这个词的人不是我们的用户，转化过来变 1 星差评 | **完全不用** | `art appraisal` / `art value` / `skip the line` |
| **③ 标题预算** | 30 字符零和，放不下 | **照常用**，只是不放最贵的位置 | `audio guide`、FR 的 `scan` |

**只有 ③ 跟竞品有关，而 ③ 不是"不用"。**

### 为什么"高频词不用会搜不到"在 Play 上不成立

Play **全文索引 4000 字符的完整描述**（iOS 不索引描述，这是两个平台最大的差别）。所以：

- **词写进完整描述 = 已被索引 = 用户搜得到。** 竞品用不用完全不影响这一点。
- Title 的作用是**权重**，不是**有无**。放进 Title 只是排得更靠前，不放也照样出现。
- ⇒ **除了 ①② 两类，所有相关词一律写进完整描述**。本轮 EN/FR 的关键词矩阵正是这么做的 —— `audio guide`、`recognition`、`painting`、FR 的 `reconnaissance` 全部在完整描述里，一个都没漏。

> **一句话**：竞品强不强，只影响"要不要花 30 字符里的一个去跟它抢"，**从不影响"这个词写不写"**。

---

## 关键词分组与评估

### 1. 品牌词

| Keyword | 供给侧竞争 | 相关性 | 判断 |
|---|---|---|---|
| gomuseum | 无 | 100 | 必然自动覆盖，无需布局 |

零真实用户 ⇒ 品牌词零搜索量，**本轮不投入任何字符预算**。

### 2. 博物馆专名词（**最高意图**）

| Keyword | 实测证据 | 判断 |
|---|---|---|
| **louvre** | `louvre guide` 返回 30+ 结果，但**头部评分 2.9–3.7**，无识别类玩家 | ⭐ **一级目标**。高意图 + 在位者弱 |
| **louvre guide** | 同上 | ⭐ 一级 |
| **louvre audio guide** | `museum audio guide` 仅 8 结果，其中 Louvre Museum Free Guide 2.9★ | ⭐ 一级，比预想的好打 |
| musée d'orsay / orsay | `louvre guide` 结果中 Orsay Museum Free Guide **1.6★** | 二级。在位者极弱但词本身量小 |
| orangerie / petit palais | 未单独检索 | 三级，仅放 Full desc |

⚠️ **合规**：Play 允许在描述中提及你的 App 覆盖的真实地点，但**不得让用户以为这是官方 App**。竞品 `Louvre Chatbot Guide` 的做法是在描述里直写 "unofficial"。GoMuseum 采用同等做法（见 metadata 的 independent-guide 声明）。**标题里出现 "Louvre" 本身不违规**（大量在位者都这么做），但不可写成 "Louvre Official" 之类。

### 3. 博物馆导览词

| Keyword | 实测证据 | 判断 |
|---|---|---|
| **museum audio guide** | **仅 8 个结果**，izi.TRAVEL/Bloomberg/GuidiGO **均未出现** | ⭐ 一级。**推翻了"红海"的既有判断** |
| museum guide | 未单独检索 | 二级 |
| paris museum guide | `guide musée paris`(FR) 拥挤；EN 侧未单独检索 | 二级 |
| audio guide | 泛词，量大意图弱 | 三级，Full desc 自然覆盖 |

### 4. 艺术品识别词（**功能词**）

| Keyword | 实测证据 | 判断 |
|---|---|---|
| art recognition | 头部 Google A&C 4.2、Smartify 4.6 | 🟡 **不作为主攻**。有强在位者 |
| painting identifier | `scan painting identify` 返回 10+ 识别 App | 🟡 **且意图错位**——多为估值 App |
| artwork recognition | 同上 | 🟡 |
| **scan**（作为修饰词） | `louvre guide` 结果中**零识别玩家** | ⭐ **一级，但只在与 louvre 组合时** |

> **本轮最重要的关键词判断**：
> 单独的识别功能词（`art recognition` / `painting identifier`）**不是 GoMuseum 的获客词** —— 那里的流量意图是"我这幅画值多少钱"，转化过来也不是我们的用户。
> 但 **`louvre` × `scan` 的组合是真空**。所以 scan 的正确用法是**修饰专名**，不是独立主攻。

**直接回答 brief §五的提问**："用户是否会主动搜索 art recognition / painting identifier？"
→ **会，而且有足够多的 App 在供给侧抢这个词** —— 说明存在需求。**但这批需求里相当一部分是艺术品估值意图，不是看展意图**（证据：结果里 Art Appraisal: Scan & Value 4.1、Art Identifier & **Value** 4.0、Estimation Tableau 等的存在与排名）。
→ **即便用户不搜识别功能词，该功能仍应作为页面转化卖点**：F5 的竞品用户原话证明"找不到作品是什么"是真实且被反复抱怨的痛点。**这正是"搜索获客关键词"与"页面转化卖点"必须分开的原因**，也是本轮结论。

### 5. 巴黎旅行场景词 / 长尾高意图词

| Keyword | 判断 |
|---|---|
| paris museum app | 二级，Full desc |
| things to do in paris | ✗ 不建议。泛旅游词，与 App 功能距离太远 |
| louvre mona lisa | 三级，Full desc 自然出现（作品名） |
| **louvre without audio guide rental** | ⭐ 长尾高意图，对应 F5/竞品差评主题，Full desc 用整段承接（`NO RENTAL, NO QUEUE`） |
| skip the line louvre | ✗ 不建议。我们不卖门票，会带来错配流量与差评 |

### 6. 不建议使用的词

| Keyword | 原因 |
|---|---|
| AI / AI guide / AI audio guide | 用户 2026-09-13 拍板；且 F6 实测显示 "AI" 在本类目已是**差评词** |
| official louvre / louvre official | 合规红线 |
| art appraisal / art value / art worth | 意图错配，会招来估值用户 → 差评 |
| free tickets / skip the line | 不提供该功能 |
| offline / offline guide | **产品当前不支持**（F7）。竞品的头部卖点，但我们写了就是失实 |

---

## 关键词布局（EN）

| Keyword | Title | Short desc | Full desc | 说明 |
|---|---|---|---|---|
| louvre | ✓ | ✓ | ✓ 多次 | 最高意图专名，三字段全覆盖 |
| guide | ✓ | | ✓ | 承接 `louvre guide` / `museum audio guide` |
| scan | ✓ | ✓ | ✓ | 差异化 + 与 louvre 组合的真空位 |
| orsay | | ✓ | ✓ | 二级专名 |
| audio guide | | | ✓ | 全文索引即可，不占 Title |
| artwork / painting / sculpture | | ✓(art) | ✓ | 语义相关词，自然覆盖 |
| recognize / recognition | | | ✓ | 功能词变体，Full desc |
| orangerie / petit palais | | | ✓ | 三级专名 |
| paris | | | ✓ | 场景词 |

**Title 取舍说明**：30 字符只够放 3 个实义词。选中 `Louvre + Guide + Scan` 的理由是三者分别承接**最高意图专名**、**最大流量词根**、**唯一零竞争差异化词**。被舍弃的是 `Orsay`（量小）与 `Audio`（可由 Full desc 索引承接）。

> **与 FR 的布局差异**：见 `keyword-research-fr-FR.md`。核心差异是 **scan 在 EN 进 Title、在 FR 不进 Title** —— 因为 Smartify 在 FR 已占住识别词（F4）。

## 需求代理验证（2026-09-25）

Google 自动补全（`gl=us` / `gl=gb`，`hl=en`，代理指标，不给量级）：`louvre audio guide` 的联想为 free / worth it / reddit / app / 3ds / price；`louvre audio guide app` 在 US、GB 都出现。⇒ ① `audio guide app` 是真实存在的查询形态，与短描述用词一致；② 用户在和官方租借（3DS）比价与口碑；③ Reddit 是他们查证的地方。
⚠️ `louvre guide` 的联想几乎全是真人导览与门票（`guided tour` / `skip the line`）——**Web 侧意图偏向真人导览**，标题里的 `Louvre Guide` 在 Play 内是否同样被这样理解未知，标题不可 A/B，交给 Search terms 报告。
EN 的 Trends 对比未取到（限流）。法语侧完整结论见 `keyword-research-fr-FR.md` 同名章节。

## 仍需真实数据验证的假设

1. `louvre guide` 与 `museum audio guide` 的**实际搜索量之比** —— 本轮只知供给侧强弱，不知需求侧大小。发布后看 Play Console 的 Search terms 报告。
2. `scan` 进 Title 是否真能带来 `louvre scan` 类长尾曝光 —— 只有上线后才能观测。
3. `TourLens: Louvre Guide` 是否真做识别 —— 若是，`louvre` × `scan` 的"真空"判断需要收回。
