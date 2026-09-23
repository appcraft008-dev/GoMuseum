# GoMuseum · Final Metadata — English (Google Play)

**状态：草案，未上传，等待用户审核。**
依据 `keyword-research-en-US.md`（实测 2026-09-21）与 `app-marketing-context.md` §3（prod DB 实测覆盖量）。
字符数为脚本实测值（Python `len()`），非手数。

---

## Title（上限 30）

| 版本 | 文案 | 字符数 | 关键词 / 定位差异 |
|---|---|---|---|
| **推荐** | `GoMuseum: Louvre Guide & Scan` | **29/30** | 三个实义词各司其职：`Louvre`=最高意图专名、`Guide`=承接 `louvre guide`+`museum audio guide` 两个词根、`Scan`=唯一零竞争的差异化词（`louvre guide` 结果里无任何识别类 App）。30 字符能同时吃下获客词和差异化词，这是最优密度。 |
| 备选 A | `GoMuseum: Louvre Audio Guide` | 28/30 | **纯获客取向**。精确匹配最高意图查询，且该词在位者仅 2.9–3.7★。代价：标题里放弃差异化，正面撞 50K–100K 安装量的在位者，新 App 零安装信号，短期难排上去。 |
| 备选 B | `GoMuseum: Scan Louvre Art` | 25/30 | **纯差异化取向**（= 上一版推荐）。能立刻占住 `louvre scan` 类零竞争长尾，但放弃 `guide` 这个最大词根，且浪费 5 个字符。 |

**取舍逻辑**：备选 A 短期打不动（Play 排名重安装与互动信号，我们是 0 基线）；备选 B 覆盖面太窄。推荐版把两者都装进 30 字符，是零成本的折中。

✅ **TourLens 已查清（2026-09-21），推荐不变**：它确实做扫描识别（标语 "Scan Anything to Listen"），所以**"零竞争"的说法收回**；但它 1K 下载、零评分零评论、2024-09 后未更新、部分设备不可用 —— 不构成排名障碍。**它零评分还能排 `louvre guide` 第 6，反而印证该词防守极弱**，`Scan` 继续留在 Title。

---

## Short Description（上限 80，**Play 索引此字段**）

| 版本 | 文案 | 字符数 |
|---|---|---|
| **推荐** | `Scan art at the Louvre or Orsay — no title or number needed, just listen.` | **73/80** |
| 备选 A（= 既有稿） | `Scan artwork at the Louvre & Orsay for an instant museum audio guide.` | 69/80 |
| 备选 B | `Point your camera at any artwork in the Louvre. Hear its story in seconds.` | 74/80 |

**为什么改掉既有稿**：既有稿（备选 A）只说了*做什么*，推荐版说的是*为什么需要它* —— "no title or number needed" 直接命中 F5 那条竞品用户原话描述的断点（墙上没有馆藏号 ⇒ 传统导览失效）。关键词覆盖不降（scan / art / Louvre / Orsay 全在）。
**为什么否决备选 B**：含 "any artwork"，而 brief §四明令绝对化表达必须先验证覆盖能力。**这条否决仍然成立，但理由要换**——不是"讲解只有 665 件"（那条已撤销），而是**识别靠图，27,221 件里只有 14,106 件有图**，约 13,000 件压根扫不到。边界在图，不在讲解。

**决策延续（2026-09-13 用户拍板）：不用 "AI" 字样做卖点。** 本轮实测为这条决定找到了外部证据：同类目竞品差评里 "probably AI writing" 已被用户当作贬义（见 competitor-analysis F6）。

---

## Full Description（上限 4000，**Play 全文索引**）

> ⭐ **这个字段有两个不同的读者，必须分开写**（2026-09-21 补写，用户提问"这段被仔细读的概率是不是不高"引出）：
>
> | 部分 | 读者 | 要求 |
> |---|---|---|
> | **第一段（约 150 字符）** | **人**。商店页折叠，用户先看到约两三行，多数不点"展开" | 必须独立扛住定位。**这是除截图外唯一被人读到的描述文字** |
> | 其余约 1900 字符 | **Play 的索引器** | 自然覆盖关键词（Play 惩罚堆砌），不必追求可读性 |
>
> 🔴 **首版在这里犯了错**：开头写的是"四馆一个 App"（方向B，我们自己判定差异化弱的那个），而真正的钩子"你不需要知道它叫什么"在第二段——**正好在折叠线下面，没人看得到**。已改为钩子前置。
> 副作用是好的：`Louvre` 现在出现在**第一句**，而靠前位置的关键词权重更高，索引也更划算。

```
Most works at the Louvre carry no number on the wall, and the label is in French. GoMuseum tells you what you're looking at — just point your camera.

The usual tricks fail here: you can't type a number into a rented audio guide, and you can't search for a name you don't know. GoMuseum removes that step — point your camera at the painting, sculpture or object in front of you, and it names the work and narrates its story. It covers the Louvre, Musée d'Orsay, Musée de l'Orangerie and Petit Palais — four Paris museums, one app.

SCAN & LISTEN
• Point your camera — GoMuseum recognizes the work and names it in seconds
• In-depth written guides for thousands of works across the four collections — grounded in verified sources, sourced, never invented
• Narrated audio, so you can listen while you look
• Not written up yet? Scan it anyway — GoMuseum researches that work and writes its guide on the spot
• Curated questions and answers for many works, written and checked in advance — not a live chatbot

EXPLORE FREELY
• Search a museum's collection by artwork or artist name
• No account needed — start scanning as a guest
• Your first 5 artwork scans and your first audio guide are free
• Written guides in 10 languages: English, French, German, Spanish, Italian, Polish, Japanese, Korean, and both Simplified and Traditional Chinese

NO RENTAL, NO QUEUE
Skip the audio-guide counter and the deposit. GoMuseum lives on your phone and follows whatever room, or whatever painting, catches your eye — not a fixed route someone else picked.

PARIS CITY PASS
One pass unlocks unlimited scans and audio across the Louvre, Orsay, Orangerie and Petit Palais for the length of your visit. One payment, not a subscription.

PRIVACY FIRST
Photos are used only to recognize the artwork in front of you. We never store or upload your original images.

GoMuseum is an independent guide. It is not affiliated with, endorsed by, or connected to the Louvre, the Musée d'Orsay, the Musée de l'Orangerie or the Petit Palais.

Note: GoMuseum needs an internet connection to recognize artworks and stream audio guides.
```

**字符数：2103/4000（53%）**（既有稿实测 1261/4000，32%）

### 较既有稿的实质变化

| # | 变化 | 依据 |
|---|---|---|
| 1 | ⭐ **保留 "thousands of works"，但把"数字"换成"机制"**——新增 `Not written up yet? Scan it anyway — GoMuseum researches that work and writes its guide on the spot` | 我曾判定该表述失实（据 `ready 665 / stub 26,556`），**判错并已撤回**：`pipeline.py` 实测懒生成 TTFC 16–18s→约 20 秒，`ready/stub` 是缓存冷热不是有无。数字会随上新馆持续过期，机制不会，且这是竞品没一个能说的话 |
| 2 | 🔴 **"10 languages" 移出 `SCAN & LISTEN`，移入 `EXPLORE FREELY` 并限定为 "Written guides in 10 languages"** | 实测：文字讲解 10 语齐整；音频除 en/fr/zh 外各语仅约 36 件。原位置紧跟音频条目，读起来像"10 语音频" |
| 3 | 🟢 **新增第二段"为什么需要它"** | 直接复述 F5 的竞品用户原话所描述的断点。这是全篇唯一一段讲用户处境而非产品功能的文字，也是转化的支点 |
| 4 | 🟢 **音频条目去掉数量限定** | `lazy_audio` 已全覆盖，音频同样按需生成，"200+" 与讲解数一样是缓存快照 |
| 5 | 🟢 预设问答加 **"not a live chatbot"** | brief §四 明令不得让用户误解为实时自由问答。主动划清比只是"不提"更安全 |
| 6 | 🟢 City Pass 加 **"One payment, not a subscription"** | 竞品差评主题里"付了钱还被要求再付"反复出现（TourBlink、MUSEUM BUDDY 各一条）。这是针对既有疑虑的直接安抚 |
| 7 | 🟢 独立声明扩写为 **not affiliated with, endorsed by, or connected to** + 逐馆点名 | Petit Palais 属 Paris Musées 体系；竞品 `Louvre Chatbot Guide` 亦自写 "unofficial"，属类目常规 |
| 8 | 🟠 **新增末尾联网提示** | F7：产品全程依赖网络，而竞品把 offline 当头部卖点、实测馆内网络很差。写在末尾管理预期，防 1 星差评；**绝不能反过来写 offline** |

---

## Keyword Coverage Matrix

| Keyword | Title | Short desc | Full desc | 覆盖 |
|---|---|---|---|---|
| louvre | ✓ | ✓ | ✓（多次） | 全覆盖 |
| guide | ✓ | | ✓（多次） | Title + Full |
| scan | ✓ | ✓ | ✓（多次） | 全覆盖 |
| orsay | | ✓ | ✓ | Short + Full |
| art / artwork | | ✓ | ✓ | Short + Full |
| audio guide | | | ✓ | Full only（刻意不占 Title，由全文索引承接） |
| recognition / recognizes | | | ✓ | Full only |
| painting / sculpture | | | ✓ | Full |
| paris | | | ✓ | Full |
| orangerie / petit palais | | | ✓ | Full |

## Before / After

| 字段 | 既有稿 | 本轮推荐 | 变化 |
|---|---|---|---|
| Title | `GoMuseum`（8/30） | `GoMuseum: Louvre Guide & Scan`（29/30） | 零关键词 → 三个实义词 |
| Short desc | 69/80 | 73/80 | 从"做什么"改为"为什么需要"，关键词不减 |
| Full desc | 1261/4000（32%） | 2103/4000（53%） | 新增痛点段 / **按需生成那句** / 订阅澄清 / 联网提示；"10 语"归位到文字讲解 |
