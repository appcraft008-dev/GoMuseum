# GoMuseum · Pre-launch Draft Audit（Google Play）

## 审计口径（brief §七）

| 类别 | 状态 |
|---|---|
| ① 当前 Google Play 线上页面 | **不存在**。`https://play.google.com/store/apps/details?id=com.gomuseum.app` → **HTTP 404**（实测 2026-09-21，en_US）。Console 上 v39 在内测轨道，未推正式轨道，故公开页面不可达。 |
| ② 项目中保存的草稿 | `docs/play-assets/store-listing/en-US.md`、`fr-FR.md` —— **只读输入，本轮未修改** |
| ③ 本轮建议 | `metadata-final-en-US.md`、`metadata-final-fr-FR.md`、`creative-brief-en-fr.md` |

**本报告是 Pre-launch Draft Audit**，审的是 ②，不是 ①。文中任何评分都不代表线上现状。

---

## 评分卡（对象 = 本地草稿 ②）

```
Overall: 41/100

Title:              2/10  ██░░░░░░░░   草稿只有 "GoMuseum"，30 字符预算用了 8，零关键词
Short description:  7/10  ███████░░░   69/80，覆盖 scan/louvre/orsay，结构好
Full description:   3/10  ███░░░░░░░   1227/4000（31%），且含失实表述（见 A1）
Screenshots:        6/10  ██████░░░░   EN/FR 各 8 张已就位，但排序未定、Slot 1 未定稿
Feature graphic:    7/10  ███████░░░   三语定稿已存在，信息与定位一致
Ratings:            0/10  ░░░░░░░░░░   零评分零评论（未发布，非缺陷）
Icon:               —              本轮未审
Conversion signals: 2/10  ██░░░░░░░░   无 What's New、无实验、无自定义页
```

Title 与 Full description 是两个最大缺口，也是 Play **唯一两个高权重可索引字段**里的浪费。

---

## 发现（按严重度）

### ~~🔴 A1. 草稿含失实的覆盖量表述~~ → ❌ **本条已撤销，我判错了**（2026-09-21 修正）

**撤销理由**：我用"库存"的框架去衡量一个**按需生成**的系统。
`backend/app/services/enrichment/pipeline.py` 的代码注释里有项目自己的实测值：**懒生成 TTFC 16–18s → 约 20 秒**，"只有第一个看到这件作品的人要等，描述落库后永久复用"。`lazy_audio` 同样已全覆盖，音频也是按需生成。

⇒ **ready 665 / stub 26,556 测的是缓存预热状态，不是用户能拿到什么。** 用户扫一件未生成的作品，等约 20 秒就有讲解 —— 那是加载过程，不是缺内容。
⇒ **"thousands of works" 描述的是系统能力，覆盖整个 27,221 件目录，表述成立。** 原判定（失实、政策风险）**不成立，撤回**。

**留作教训**：`ready/stub` 这两个字段名天然诱导"有/没有"的二分读法，而在懒生成架构下它们只是"热/冷"。**凡是按需生成的系统，覆盖率分母都别按库存算。**

> 下方原始记录保留，供追溯我当时看到了什么、错在哪。

### 📌 A1（原始记录，结论已撤销）

| 文件 | 原文 | 实测真值 |
|---|---|---|
| `en-US.md` L22 | "Full text guides for **thousands of works** across all four museums" | **665 件**（EN） |
| `fr-FR.md` L21 | "Guides texte complets pour **des milliers d'œuvres** dans les quatre musées" | **656 件**（FR） |

prod DB 实测：`content_status` = **ready 665 / stub 26,556**。详见 `app-marketing-context.md` §3.1。

Google Play 政策要求商店描述与 App 实际功能一致；"thousands of works" 与真实的 665 件差一个数量级。
**处置**：本轮 metadata 全部改为 "650+ works" / "200+ narrated"，并对剩余部分给出诚实且有说服力的表述（识别给身份、讲解逐步补全）。

> ⚠️ 这两份是 brief §十三 指定的**只读输入，本轮未改动**。

### ✅ 用户裁定（2026-09-21）：源文件不改

**理由**：文本与音频**都有懒生成机制**，几千件并非做不到，只是需要多等一会儿；且用户正在持续灌入音频。
⇒ `docs/play-assets/store-listing/*.md` 保持原样，**"thousands of works" 不回改**。

**我实测到、但当时没算进这条判断的三个约束**（留档，不重复争论）：

| 约束 | 代码位置 | 何时绑定 |
|---|---|---|
| `_LAZY_DAILY_SECTION_CAP = 300` 段/天，**全局** | `services/enrichment/lazy.py:22` | 零用户时不绑定；规模化后绑定 |
| `_SEM = threading.Semaphore(2)`，进程级并发 2 | 同文件 `:19` | 同上 |
| 只对**已鉴权调用方**点火（匿名读得到已有内容，但不触发生成） | `endpoints/museums.py:115` | 始终 |

⇒ **对当下单个用户，用户的判断成立**（前端会轮询，等一会儿确实能拿到）；**风险在规模化之后**，不在现在。此事按用户裁定执行，将来真有流量时再回看。

### ✅ 已结：新 metadata 不写数字，改讲机制

我原先坚持写 `650+`，理由是"审核员随机扫一件会落到 stub"。**该理由基于错误前提，见上方 A1 撤销**——约 20 秒就生成好了。

最终处置：**两个数字（650+ / 200+）全部从文案移除**。理由不是在两个数之间选，而是**它们都是库存快照，而这不是库存系统**：
- 数字会随上新馆、新藏品、用户点击持续变化 → 写进商店文案就是**在维护一个必然过期的数**
- 更关键：**讲机制比讲数字强**。竞品没有一个能说"没写过的作品，扫了当场给你写一份"

改后（EN）：
```
• In-depth written guides for thousands of works across the four collections — grounded in verified sources, sourced, never invented
• Narrated audio, so you can listen while you look
• Not written up yet? Scan it anyway — GoMuseum researches that work and writes its guide on the spot
```
第三条是**整份文案里最强的一句**，而且它是我原先那套保守写法永远写不出来的。

### 🔴 A2. "10 种语言"被放在音频语境里，读起来像"10 语音频"

`en-US.md` L23 的语言条目位于 `SCAN & LISTEN` 区块内，紧跟两条音频条目之后。实测：**文字讲解确为 10 语齐整（各语约 656 件）；音频除 en/fr/zh 外各语仅约 36 件。**
**处置**：本轮把语言条目移出音频区块，并明确限定在"written guides"。

### 🔴 A3. Title 浪费 22 个字符

Play 的 Title 是权重最高的可索引字段，草稿只写 "GoMuseum"（8/30）。零关键词。
**处置**：见 `metadata-final-*.md`，EN/FR 各给推荐 + 2 备选。

### 🟠 A4. Full description 只用了 31% 预算，且 Play **全文索引**

iOS 的描述不索引，Play 的索引 —— 草稿是按 iOS 习惯写的。1227/4000。
**处置**：EN 扩到约 2000 字符，每一句都对应真实功能或差异化点，不堆砌。

### 🟠 A5. 既有调研笔记里两条结论已被本轮实测推翻

`en-US.md` 开头与 `fr-FR.md` 开头的调研注记称：audio guide 类目被 izi.TRAVEL / Bloomberg Connects / GuidiGO 饱和，且"none of them do photo recognition"、识别位置"largely unclaimed"。

本轮实测（详见 `competitor-analysis-en-fr.md` F1/F2）：
- `museum audio guide`（en_US）仅 8 个结果，**上述三者均未出现**；
- 识别类 App 在 `scan painting identify` / `art recognition` 下**至少 10 个**，FR 更有 Smartify 4,6★ 排第 1。

**建议修正**：把"识别无人做"改为**"没有任何巴黎博物馆导览 App 做现场识别"** —— 后者本轮实测成立（`louvre guide` 结果中零识别玩家），且是更准确、更可辩护的说法。

### 🟠 A6. 类目建议：Travel & Local

Smartify 选 Education；TourBlink 与 MUSEUM BUDDY 均选 **Travel & Local**。GoMuseum 的用户场景（在巴黎旅行）与后者一致，**建议 Travel & Local**。本轮未做类目 A/B 建议（新 App 无基线）。

### 🟡 A7. 缺 What's New / 实验 / 自定义页

均为发布后动作，记录于 `experiment-and-measurement-plan.md`，非当前阻塞。

### 🟢 A8. 草稿做对的部分（不要动）

- Short description 69/80，同时覆盖 scan + louvre + orsay 且读起来自然 —— **本轮只微调，不推翻**。
- `PRIVACY FIRST` 段（照片仅用于识别、不存储不上传）：Play 的 Data safety 表单与描述**必须一致**，这段保留。
- FR 稿不是 EN 的机翻，已有独立表达 —— 符合 brief §三。

---

## Quick Wins（可立即实施）

1. 改 Title（EN/FR），把 30 字符预算用满 —— 零成本、影响最大。
2. 删掉 "thousands of works" / "des milliers d'œuvres"，换成实测数字。
3. 把"10 种语言"移出音频区块。
4. Full description 扩容到 2000 字符量级。

## 需要产品侧配合（ASO 修不了）

1. **离线能力缺口**（F7）：竞品把 offline 当头部卖点，而 GoMuseum 全程依赖网络，馆内网络实测很差。**在有离线能力前，文案不得承诺 offline。**
2. **`TourLens: Louvre Guide` 未核实**：疑似唯一正面直接竞品，上传前必查。
3. **Data safety 表单需与 `PRIVACY FIRST` 文案逐条对齐**（Play 会比对）。
