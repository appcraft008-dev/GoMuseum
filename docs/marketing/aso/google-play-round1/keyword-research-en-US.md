# GoMuseum · Keyword Research — English (Google Play)

**当前无真实搜索量/难度数据**（无 Appeeky 等付费 ASO 数据源）。以下 Volume/Difficulty/Relevance 全部基于搜索结果数量、竞品覆盖密度、语义相关性的**方向性判断**，非真实检索量，检索日期 2026-09-08，来源见 `competitor-analysis-en-fr.md` 及本文件末尾 Sources。

## 关键词分组

### 品牌词
- gomuseum

### 博物馆名称词
- louvre, louvre museum, musée d'orsay / orsay museum, musée de l'orangerie / orangerie museum, petit palais

### 博物馆导览词
- louvre guide, louvre audio guide, museum audio guide, paris museum guide, orsay guide

### 艺术品/画作识别词
- art recognition, artwork recognition, painting identifier, art scanner, scan artwork, identify painting

### 巴黎旅行场景词（长尾）
- louvre without audio guide rental, skip the audio guide line louvre, one day at the louvre, free things to do at the louvre, louvre app instead of audio guide

## Top Keywords by Opportunity（方向性判断）

| Keyword | Volume(推测) | Difficulty(推测) | Relevance | Opportunity | 依据 |
|---|---|---|---|---|---|
| louvre guide | 75 | 80 | 90 | 中 | 至少6款直接竞品命中（vusiem/tourblink系列+izi.TRAVEL+Bloomberg Connects），竞争激烈但意图极强 |
| louvre audio guide | 70 | 82 | 75 | 中低 | 竞争同上，但"audio guide"和我们的"scan"定位有语义错位，转化后体验落差风险 |
| museum audio guide | 60 | 60 | 55 | 中 | 泛词，竞争密度低于"louvre"专名但意图不如专名精确 |
| art recognition | 50 | 55 | 85 | 中高 | 本轮新发现至少5款通用识别App在争这个词（ArtScan、Art Identifier、Painting & Art Identification、Painting Identifier AI Scanner），但**都不绑定任何博物馆** |
| painting identifier | 45 | 50 | 80 | 中高 | 同上，通用识别类竞品密集但无博物馆场景锚定 |
| scan artwork louvre | 20 | 15 | 95 | **高** | 复合长尾词，几乎无直接竞品同时命中"scan/识别"+"louvre"，是本轮验证到的最干净空位 |
| louvre app instead of audio guide rental | 15 | 10 | 90 | **高** | 场景词，直接命中我们商店文案已有的差异化叙事（"no rental, no queue"），竞争几乎为零 |
| free things to do at the louvre | 30 | 25 | 40 | 中 | 泛旅行攻略词，意图偏"信息查找"而非"下载App"，转化率存疑，落地页更适合承接（已有 `deployment/website/`） |

## 关键词分层

**Primary（3-5，标题/短描述必须覆盖）：**
1. louvre（专名，最高意图）
2. scan / recognition（功能差异化词，二选一或都用，视字符预算）
3. audio guide（照顾"louvre audio guide"这类高流量泛词，即使定位不完全一致也要留一点入口流量）

**Secondary（短描述/完整描述前段）：**
- musée d'orsay / orsay, orangerie, petit palais, art recognition, painting

**Long-tail（完整描述自然分布，4000字符里有大量空间）：**
- scan artwork louvre, louvre app instead of audio guide rental, identify painting, museum guide app, paris museum guide

**Aspirational（当前不主攻，随体量增长再评估）：**
- museum audio guide（泛词，被 izi.TRAVEL/Bloomberg Connects 这类大平台占据，短期难撼动）

## 与 Phase 2 竞品分析交叉验证

- "louvre guide"类专名词竞争度**高于本轮最初预期**（新发现的 vusiem/tourblink 系列把这个词打得更拥挤了）——不该把标题预算全押在这上面
- "art recognition"类功能词竞争度**也高于最初预期**（新发现一批通用识别App）——但没有一个绑定Paris四馆，"scan artwork louvre"这类复合长尾词才是真正干净的空位，这是本轮最重要的关键词发现，比既有资料里"scan是空位"的判断更精确

## Recommendations

1. 标题（30字符）应该同时容纳"louvre"专名+"scan/recognition"功能词，而不是二选一——具体版本交给 Phase 3 `metadata-optimization`
2. 完整描述里明确写出"scan artwork"这类复合长尾词的自然变体（如"scan any painting at the Louvre"），这是本轮验证到的最高机会分关键词
3. 落地页（`deployment/website/index.html`，已发布前状态）比商店描述更适合承接"free things to do at the louvre"这类信息查找型长尾词，两者分工不要混淆

## Sources
- [ArtScan - Identifier Tableaux](https://apps.apple.com/us/app/artscan-identifier-tableaux/id6630371903)
- [Art Identifier App](https://apps.apple.com/us/app/art-identifier/id6747607478)
- [Painting & Art Identification - Google Play](https://play.google.com/store/apps/details?id=com.seapps.artidentification&hl=en_US)
- [Painting Identifier AI Scanner](https://apps.apple.com/us/app/id6751956074)
- 其余竞品来源见 `competitor-analysis-en-fr.md`
