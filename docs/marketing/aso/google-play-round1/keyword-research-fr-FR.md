# GoMuseum · Recherche de mots-clés — fr-FR (Google Play)

> **当前无真实搜索量/难度数据，以下判断基于搜索结果数量、竞品覆盖、在位者评分与语义相关性，属于方向性判断。**
> 数据来源：Google Play 网页搜索实访（`hl=fr_FR&gl=FR`），检索日 **2026-09-21**。
> **本文件不是 en-US 的翻译。** 法语关键词独立检索、独立评估，结论与英语**相反**。

---

## 本轮最重要的法语市场发现

实测三个法语查询，得到与英语市场**结构相反**的格局：

| 查询 | 结果强度 | 头部在位者 | 含义 |
|---|---|---|---|
| `reconnaissance œuvre d'art` | 强 | **Smartify 4,6★ 排第 1**，后接 ArtScan、Artly 4,5、DailyArt 4,7、Google Arts & Culture | 🔴 **识别词在法语已被占住** |
| `audioguide louvre` | **弱，仅 8 个结果** | MUSEUM BUDDY **2,5★** / Louvre Chatbot 4,5 / TourBlink 4,3 / Orsay Free Guide **2,0★** | ⭐ **这才是法语空位** |
| `guide musée paris` | 拥挤但错位 | Odyssey 4,2 / Civitatis 4,7 / CityMaps2Go 4,4 / **Paris Musées 官方系列** | 🟡 被城市指南和官方 App 占据 |

> **结论（brief §五要求的"判断方向A在法文市场是否同样成立"）：**
> **不成立。** 英语市场里"识别"是可占的差异化角度；法语市场里它正面撞上 Smartify（4,6★、1M+ 下载、两周一更新）。
> **法语市场应改用 `audioguide` / `guide du Louvre` 做搜索获客，把 scan 降为页面转化卖点。**
> 这是有证据的市场差异，不是把英语结论翻译一遍。

---

> ⭐ **重要澄清**：上面说"识别词不主攻"**不等于不用这些词**。`reconnaissance`、`reconnaît`、`scanner`、`tableau` 全部写进完整描述并被 Play 索引 —— 见文末覆盖矩阵。
> Smartify 的存在只影响"要不要花法语标题 30 字符里的一个去跟它抢"，**不影响这些词写不写**。判据全文见 `keyword-research-en-US.md` 开头「排除一个关键词，只有三种正当理由」。

## 法语用户的实际表达方式（brief §九 要求）

| 形态 | 实测观察 | 布局决定 |
|---|---|---|
| **`audioguide` 连写** | Play 查询 `audioguide louvre` 返回正常结果集；法语用户普遍连写 | ✓ 采用连写形式进 Title |
| `audio-guide` / `audio guide` 分写 | 词典形式，但用户输入更常连写 | Full desc 里两种形态各出现一次，兼容 |
| **重音 `musée`** | Play 结果对 `musée` / `musee` 通常互通，但**标题里必须写正确的 `musée`** | ✓ 正字法完整，不去重音 |
| **`œuvre` 连字 vs `oeuvre`** | 用户实际输入多为 `oeuvre`；正式文案须用 `œuvre` | ✓ 文案用 `œuvre`，Full desc 自然出现一次 `oeuvre` 变体以兼容 |
| **单复数** | `guide musée paris` 与 `guides musées paris` | Full desc 覆盖单复数两形态 |
| **`tableau` vs `peinture`** | `Estimation Tableau & Peinture` 出现在识别结果里 ⇒ 两词法语用户都用；`tableau` 更口语 | ✓ Full desc 两词都出现 |
| **馆名本地形式** | 必须是 `Musée d'Orsay`、`Musée de l'Orangerie`、`Petit Palais` | ✓ |

⚠️ **`Petit Palais` 的歧义**：`musée du Petit Palais` 是阿维尼翁的；巴黎的正式名是 **`Petit Palais, musée des beaux-arts de la ville de Paris`**。商店文案用短名 `Petit Palais` 即可，但**任何需要精确匹配的场合不能用 `musée du Petit Palais`**。

⚠️ **`Louvres` 是个地名**：FR `louvre guide` 结果里出现了 `Ville de Louvres`（瓦勒德瓦兹省的市镇）。法语文案里写 `Louvre` 时尽量带 `Musée du Louvre` 或 `au Louvre`，避免与该市镇混淆。

---

## ⭐ 法语的 `scan` 属于 PDF 扫描器（2026-09-21 补测，修正本文件原有理由）

**起因**：用户追问"为什么法语不能用 Scan & Listen，是因为竞品用了吗？"。
两点都要认：① **法语正文里一直在用**（简短描述首词 `Scannez`、区块标题 `SCANNEZ & ÉCOUTEZ`、Feature Graphic `SCANNEZ · ÉCOUTEZ · EXPLOREZ`），本文件覆盖矩阵里那个 `✗` **只针对 Titre 一列**，行标写法有误导；② **但本文件原先给的理由是虚的** —— 我用 `reconnaissance œuvre d'art` 的结果去论证 "scan 被占"，**而那个查询里根本不含 "scan"**。属于从不含该词的查询外推。

**补测（fr_FR / gl=FR，2026-09-21）**：

| 查询 | 前排实际返回 |
|---|---|
| `scanner une œuvre` | Art Scanner with AI(1,3★)、ArtScan，**第 3 位起全是 PDF 扫描器**：iScanner 4,6★ / Scanner App PDF 4,5★ / Adobe Scan 4,6★ / CamScanner 4,6★ / PhotoScan(Google) 4,0★ / TapScanner 4,5★ / Clear Scan 4,7★ / Simple Scan 4,6★ … |
| `scan tableau musée` | ArtScan、Art Scanner、Smartify 之后：RealityScan、Scaniverse、Simple Scan PDF、CamScanner、Genius Scan 4,8★、MDScan、Scanium…… 另有 **Tableau Mobile for Intune**（Salesforce BI，法语 `tableau` 一词多义）与 `Estimation Tableau & Peinture`（估值意图） |

**结论**：法语里 `scan / scanner` 是英语借词，其 Play 地盘归**文档扫描工具**。两个查询都**带了艺术限定词**（`œuvre`、`tableau musée`）却依然返回 PDF 扫描器，信号很强。

⇒ **法语 Titre 放 `Scan` = 把自己放进 PDF 扫描器的语义邻居，还要正面对 Adobe Scan / CamScanner 这类装机量巨大的工具。** 归类为**②意图错配**（见 `keyword-research-en-US.md` 的三类判据），不是 ③标题预算，更不是"竞品用了所以躲开"。原结论（Titre 用 `Audioguide`）因此**更站得住**。

⚠️ **这不影响正文用词**：正文里有 `œuvre` / `musée` / `Louvre` 做消歧，`Scannez une œuvre au Louvre` 无歧义，照常用。
⚠️ **英语没有这个问题**：EN `scan painting identify` / `art recognition` 返回的是艺术类 App，`Scan` 留在英文 Title 不受此影响。**这是一条英法不对称，不要互相套用。**

---

## 关键词分组与评估

### 1. 馆名词（一级）

| Mot-clé | 证据 | 判断 |
|---|---|---|
| **Louvre / Musée du Louvre** | `audioguide louvre` 头部 2,5★ | ⭐ 一级 |
| **guide du Louvre** | 同上 | ⭐ 一级 |
| **audioguide Louvre** | **仅 8 结果，最弱的高意图词** | ⭐⭐ **法语市场首选** |
| Musée d'Orsay / Orsay | Orsay Free Guide **2,0★** | 二级 |
| Orangerie / Petit Palais | — | 三级，Full desc |

### 2. 导览词（一级/二级）

| Mot-clé | 判断 |
|---|---|
| **audioguide** | ⭐ 一级，进 Title |
| **guide musée** | ⭐ 一级 |
| visite guidée | 二级，Full desc。注意它也指真人导览，可能带来错配 |
| guide audio musée | 二级 |
| `guide musée paris` | 🟡 **降级**。被 Civitatis 4,7 / Odyssey 4,2 / Paris Musées 官方占据，且多为城市指南意图 |

### 3. 识别词（**法语降级为转化卖点，不作获客**）

| Mot-clé | 证据 | 判断 |
|---|---|---|
| reconnaissance œuvre d'art | **Smartify 第 1，4,6★** | 🔴 **不主攻**，Full desc 自然覆盖 |
| identifier tableau | `ArtScan - Identifier Tableaux` 已在位 | 🔴 不主攻 |
| **scanner une œuvre / scan** | ⭐ 见下方专节——**法语里这个词属于 PDF 扫描器** | 🟡 **正文/简短描述/截图照常用，不进 Title**（理由是意图错配，不是竞品占位） |
| estimation tableau | `Estimation Tableau & Peinture` 在位 | ✗ **意图错配**，估值用户，坚决不碰 |

### 4. 旅行场景词 / 长尾

| Mot-clé | 判断 |
|---|---|
| que voir au Louvre | ⭐ 长尾高意图，Full desc 承接 |
| visiter le Louvre | ⭐ 长尾，Full desc |
| Louvre sans audioguide / sans location | ⭐ 对应竞品差评主题，Full desc 整段承接 |
| billet Louvre / coupe-file | ✗ 不提供，会招错配流量 |

### 5. 不建议使用

| Mot-clé | 原因 |
|---|---|
| IA / guide IA | 用户拍板不用 "AI"；F6 显示该类目里"像 AI 写的"已是差评理由 |
| officiel / application officielle | 合规红线。**小皇宫属 Paris Musées 体系，此处尤须谨慎** |
| hors ligne / offline | **产品不支持**（F7），写了即失实 |
| estimation / valeur / expertise | 估值意图错配 |

---

## 关键词布局（FR）

| Mot-clé | Titre | Description courte | Description complète |
|---|---|---|---|
| Louvre | ✓ | ✓ | ✓ 多次 |
| **audioguide** | ✓ | | ✓ |
| guide | (含于 audioguide) | | ✓ 多次 |
| Orsay | | ✓ | ✓ |
| **scan / scanner / scannez** | **✗ 仅此列**（意图错配→PDF 扫描器） | ✓ **首词** | ✓（多次，含区块标题 `SCANNEZ & ÉCOUTEZ`） |
| musée(s) | | | ✓ |
| œuvre / tableau | | ✓(œuvre) | ✓ 两词 |
| reconnaissance | | | ✓ |
| Orangerie / Petit Palais | | | ✓ |

## EN 与 FR 布局差异（brief §十.6 要求）

| 维度 | en-US | fr-FR | 依据 |
|---|---|---|---|
| **Title 里的差异化词** | **`Scan` 进 Title** | **`scan` 不进 Title，改放 `Audioguide`** | ⭐ 真实理由是**法语 `scan` 属于 PDF 扫描器**（见上方专节实测），不是"Smartify 占了"。⚠️ 仅限 Title，正文照常用 |
| 主攻查询 | `louvre guide` / `museum audio guide` | `audioguide louvre` | FR 该词仅 8 结果，是更薄的空位 |
| 识别功能的角色 | 获客 + 转化 | **仅转化** | 同上 |
| 城市泛词 | `paris museum guide` 二级可用 | `guide musée paris` **降级** | FR 该词被官方 App 与城市指南占据 |

## 仍需真实数据验证

1. `audioguide louvre` 的真实搜索量是否足以支撑获客 —— 结果少可能意味着**供给少**，也可能意味着**需求少**。本轮无法区分。**这是本文件最大的未知数。**
2. Smartify 在 FR 的第 1 位是否稳定（单次检索快照）。
3. 法语用户输入 `audioguide` 连写的比例 —— 只有 Console 的 Search terms 报告能答。
