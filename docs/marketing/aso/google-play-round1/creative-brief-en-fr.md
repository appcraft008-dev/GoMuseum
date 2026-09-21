# GoMuseum · Creative Brief — Feature Graphic + Screenshots（EN + FR）

**本轮重做，检索/实测日 2026-09-21。** EN/FR 各 8 张主图 + 备用图的**原始 UI 抓图**已就位，上一版的两个阻塞项（`999992` 占位数据、"Ask anything" 输入框）已在素材侧修复。
⚠️ **但营销文案图层尚未合成，且新发现三个阻塞** —— 见 §四。

---

## 一、先定"要让用户一下记住什么"

这是整个 ASO 的支点，也是截图排序唯一的依据。**不是六条并列卖点** —— 商店页停留 3–6 秒，并列六条等于记住零条。正确的结构是**一句话 + 三根支柱**，三根支柱依次消解三个拒绝理由。

### 核心（唯一要被记住的一句）

> **你不需要知道它叫什么。**
> 看到哪件拍哪件，立刻知道它是什么、听它的故事。

**为什么是这句而不是"拍照识别"**：所有替代方案都卡在同一个前提上——*你得先知道你在看什么*。租来的导览器要输编号，搜索要知道名字，Smartify 要那件作品在它的合作目录里。而游客的真实状态恰恰是不知道。
**这不是我们的假设**：MUSEUM BUDDY 的一位付费用户在 2026-06 的差评里自己写明——馆里很少有作品标着馆藏号，没有 App 里的地图就没法手动找到它们（见 `competitor-analysis-en-fr.md` F5）。识别不是"多一个功能"，是把这一步整个删掉。

### 三根支柱（各消解一个拒绝理由）

| 支柱 | 消解的拒绝理由 | 证据 |
|---|---|---|
| **1 · 信得过** — 讲解基于可溯源材料，不脑补 | "AI 生成的能信吗？" | F6：TourBlink 差评原话把"像 AI 写的"当贬义，并说 Wikipedia 更有信息量 |
| **2 · 不受束缚** — 不租、不押金、不排队；你走到哪它讲到哪，不是别人排好的路线 | "跟租个讲解器比强在哪？" | F5/F7：竞品差评集中在付费失败、馆内下载不完、路线房间号错 |
| **3 · 零门槛试** — 免注册、免费额度，付费是一次性通票不是订阅 | "要花我多少钱？会不会套路？" | Smartify 最高赞差评就是注册墙挡死使用；两个竞品各有"付了还要再付"的差评 |

### 转化层（进页面，**不进前三张截图**）

四馆覆盖 · 10 语文字讲解 · 搜索找作品 · 隐私（照片不存不传）

这些是"看到加分、看不到不减分"的。和记忆层混在一起会稀释核心 —— **这正是上一版把"一站四馆"和核心定位并排放的错误**。

### ⚠️ 一条纪律：承诺的边界在「有没有图」，不在「写没写过」

~~实测 ready 665 / stub 26,556，讲解承诺只能挂在 650+ 件上~~ ——**这条判错了，已撤销**：懒生成约 20 秒补齐（`pipeline.py` 实测 TTFC 16–18s），`ready/stub` 是缓存冷热不是有无。

**真正的边界是图**：27,221 件目录里 **14,106 件有图**，识别靠图。所以：
- ✅ 可以说 "thousands of works"、"scan it and it writes one"
- ❌ 仍**不可**说 "any artwork" / "every artwork" —— 无图的那约 13,000 件识别不到
- ❌ 仍不可承诺 **offline**（F7，产品不支持）

---

## 二、Feature Graphic（1024×500px）

已有三语定稿 `docs/play-assets/feature-graphic/{en-US,fr-FR,zh-CN}.png`，内容脚本见同目录 `README.md`：品牌图标 + "GOMUSEUM" + "SCAN · LISTEN · EXPLORE" 标语，暖纸色系。

| 项 | 结论 |
|---|---|
| 核心传播信息 | **不用重做**。"SCAN · LISTEN · EXPLORE" 与本轮核心一致（动作序列，不是功能列表） |
| 推荐主标题 | 维持 `GOMUSEUM` |
| 是否需要副标题 | **EN 建议加**：`You don't need to know its name.` —— Feature Graphic 是 Play 列表页的第一视觉，把核心那句放上去比标语更有记忆点。**FR 不加**（见下） |
| 画面结构 | 维持现有暖纸色系与品牌图标 |
| 艺术品与手机界面关系 | 若重做：手机取景框对着一幅**未标注名字**的画作，画面上不出现任何作品标题文字 —— 视觉上直接演出"不需要知道名字" |
| 品牌元素 | 图标 + 字标，维持 |
| **禁止出现** | ① 任何暗示官方合作的馆徽/馆名背书；② 任何暗示实时 AI 对话的聊天气泡/麦克风图标；③ "AI" 字样；④ 具体作品的高清全画幅（版权风险，用取景框局部） |
| **法语版术语一致性** | 标语法语形式须与 metadata 的动词一致：metadata 用 `Scannez`，故标语用 **`SCANNEZ · ÉCOUTEZ · EXPLOREZ`**。✅ **2026-09-21 已打开 `fr-FR.png` 核对：实为 `SCANNEZ · ÉCOUTEZ · EXPLOREZ`，通过。** |

**FR 为什么不加那句副标题**：法语市场的获客词是 `audioguide louvre`（见 `keyword-research-fr-FR.md`），Feature Graphic 应当强化 audioguide 语境而非识别语境。建议 FR 副标题用 `Le guide qui vous suit, sans location.`（不租设备、跟着你走）。

---

## 三、商店截图排序（Play 允许 2–8 张，本轮用满 8）

排序原则：**前三张必须共同讲完"核心那句 + 支柱1"**，第 4–6 张补支柱 2/3 与覆盖面，第 7–8 张收口。

### ⚠️ 硬规则：每张 3–5 个词，大字，无副标题

**用户 2026-09-21 定：「每张图的文案 3-5 个单词，用大字！你这样写一句话根本没人看」。** 副标题一律取消——副标题必然用小字，而小字在这个尺寸下等于不存在。

⚠️ **修订记录（2026-09-21 第二次）**：我第一次执行这条规则时**把八句全改了**，而逐句数下来只有 1/2/4/6 四句超标（7-8 词），3/5/7/8 本来就是 4-5 词。结果是把 `Not a subscription` 削成 `No subscription`（丢了力度）、把 `Everything you've seen, kept.` 的 `kept` 砍掉（`kept` 才是留存这个点本身）。
**教训：规则是用来筛的，不是用来一刀切的——先数哪几句真的违规，只动那几句。**

### EN（素材：`docs/play-assets/screenshots/en-US/`）

| # | 素材文件 | 营销目标 | 主标题（3–5 词） | 词数 | 为什么是这句 |
|---|---|---|---|---|---|
| 1 | `screenshot_EN_01_home.jpg` | **Hook** | **You don't need its name.** | 5 | Slot 1 决定约 80% 的转化判断。这是**承诺**不是提问——「你不需要知道它叫什么」正是 F5 竞品用户亲口描述的断点。<br>⚠️ 曾改成问句 `Don't know its name?`，**是错的**：图上没有答案，提问就只是提问，承诺才有钩子 |
| 2 | `screenshot_EN_02_scan.jpg` | 核心机制 | **Point. That's it.** | 3 | 原为 "Point your camera — that's the whole step."（8 词）且与 Slot 1 当时的副标题重复。砍到 3 词，"就这么简单"的语气反而更强 |
| 3 | `screenshot_EN_03_result.jpg` | **支柱1 · 信得过** | **Sourced, checked — never invented.** | 4 | **保留原句**（本来就 4 词）。前三张收口，F6 证明本类目"像 AI 编的"已是成形疑虑 |
| 4 | `screenshot_EN_04_explore.jpg` | 覆盖面 | **Four museums. One app.** | 4 | 上一版列了四个馆名（7 词，小图上糊成一片）。**截图不参与索引**，所以馆名在这里没有关键词价值，只有阅读成本——砍掉 |
| 5 | `screenshot_EN_05_collection.jpg` | 内容广度 | **Thousands of works, four collections.** | 5 | **保留原句**（本来就 5 词）。不写具体数字：那是缓存快照不是能力上限（懒生成约 20 秒补齐），会随上新馆持续过期 |
| 6 | `screenshot_EN_06_indepth.jpg` | 内容深度 | **As deep as you want.** | 5 | 只留 1 张。素材里这个界面有多张重复变体，不该占多个位 |
| 7 | `screenshot_EN_07_pass.jpg` | **支柱3 · 零门槛** | **One pass. Not a subscription.** | 5 | **保留原句**。`Not a subscription` 比 `No subscription` 有力，是纠正而非陈述。两个竞品都有"付了还要再付"的差评 |
| 8 | `screenshot_EN_08_footprints.jpg` | 留存信号 | **Everything you've seen, kept.** | 4 | **保留原句**。`kept` 不能省——"看过的都留着"才是这个功能本身 |

**备用图**：`screenshot_spare_pass_top.jpg`（Slot 7 的构图备选）、`screenshot_spare_result_qa.jpg`（预设问答 —— ⚠️ brief §四 明令**不进前三张**，只能作为 Slot 6 的替代，且文案必须写明是预先准备的问答、不是实时对话）。

### FR（素材：`docs/play-assets/screenshots/fr-FR/`）

同一条 3–5 词硬规则，**法语原生表达，不是直译**（法语通常比英语长约 20%，逐字译必然超）：

| # | 素材文件 | 主标题（3–5 词） | 词数 | 法语侧说明 |
|---|---|---|---|---|
| 1 | `screenshot_FR_01_home.jpg` | **Pas besoin de son titre.** | 5 | 不逐字译。法语 `Pas besoin de connaître son titre.` 是 6 词，去掉 `connaître` 后既合规又更直接 |
| 2 | `screenshot_FR_02_scan.jpg` | **Pointez. C'est tout.** | 3 | 上一版 7 词，砍到 3 |
| 3 | `screenshot_FR_03_result.jpg` | **Sourcé, vérifié — jamais inventé.** | 4 | **保留原句**（本来就 4 词） |
| 4 | `screenshot_FR_04_explore.jpg` | **Quatre musées. Une app.** | 4 | 同 EN：馆名不进截图（截图不参与索引） |
| 5 | `screenshot_FR_05_collection.jpg` | **Des milliers d'œuvres, quatre collections.** | 5 | **保留原句**（本来就 5 词）。`œuvre` 用连字 |
| 6 | `screenshot_FR_06_indepth.jpg` | **Aussi loin que vous voulez.** | 5 | 与 EN 同构，法语这句本身就短 |
| 7 | `screenshot_FR_07_pass.jpg` | **Un pass. Pas d'abonnement.** | 4 | 原 `Un seul pass. Pas un abonnement.` 是 6 词，去掉 `seul`/`un` 后合规 |
| 8 | `screenshot_FR_08_footprints.jpg` | **Votre visite, conservée.** | 3 | 不直译——`Tout ce que vous avez vu, conservé.` 是 7 词，改用"您的参观，留存" |

**FR 备用图**：`screenshot_spare_result_qa.jpg`（无 `pass_top` 备选，与 EN 不对称，非阻塞）。

---

## 四、上传前的硬检查清单（2026-09-21 已目视核对）

| # | 检查项 | 结果 |
|---|---|---|
| 1 | Feature Graphic 法语标语与 metadata 动词一致 | ✅ **通过**。`fr-FR.png` 实为 `SCANNEZ · ÉCOUTEZ · EXPLOREZ` |
| 2 | 覆盖量文案 | ✅ 已改为能力口径（不再写数字），见 §三 Slot 5 |
| 3 | **截图是否已带营销文案图层** | 🔴 **不通过，见 B1** |
| 4 | **任一截图不得出现 "AI" 字样或聊天输入框** | 🔴 **不通过，见 B2** |
| 5 | Slot 1 是否呈现免费入口 | 🔴 **不通过，见 B3** |
| 6 | FR 截图内是否残留英文 UI | ⏳ 未逐张核对 |
| 7 | `spare_result_qa` 若启用需写明预设问答、不进前三张 | ⏳ 当前未启用 |

### 🔴 B1. 八张截图**全是原始 UI 截图，没有任何文案图层**

实际打开 `EN_01` / `EN_02` / `EN_07` 核对：三张均为设备原始截屏（带状态栏、时间、信号格），**§三表格里那 8 句主标题一句都不在图上**。

⚠️ **本文件上一版写的"素材已齐备，不用重截"是误导** —— UI 抓图确实齐了，但**营销合成没做**。而截图是整个商店页转化权重最高的位置（见 `experiment-and-measurement-plan.md` 的价值排序）。
⇒ **必须先做图层合成才能上传**，这是设计活，不是 ASO 活。

### 🔴 B2. `screenshot_EN_02_scan.jpg` 屏幕上印着 "AI"

原文：**"Recognizing… / AI is comparing with collections and public art databases"**。

这是**产品界面内的文字**，文案图层盖不住。传上去等于把 "AI" 放上商店页，违反 2026-09-13 用户决定，且 `competitor-analysis-en-fr.md` F6 实测显示本类目里"像 AI 写的"已是差评词。

**三个可选处置**（属产品/设计决策，待用户定）：
1. 改 App 内该句文案（如 "Comparing with museum collections and public art databases"）后重截 —— 最干净，但要发包
2. 换一帧：取识别**进行中但未弹出该 bottom sheet** 的瞬间重截
3. 构图时把 bottom sheet 裁切掉 / 用文案图层覆盖该区域

### 🔴 B3. `screenshot_EN_01_home.jpg` 两个问题

1. **"Pass active · full access unlocked"** —— 这是**已付费账号**的状态。Slot 1 是 Hook 位，应当呈现免费入口（"first 5 scans free"），而不是一个已解锁的账号。
2. **"Nearby M…" 被截断** —— 可见的 UI 溢出缺陷，出现在最重要的那张图上。

### 已被用户明确搁置，不要再提

付费墙截图的币种（`EN_07` 显示 £7.99；定价策略待用户在 Console 内测试）、FR 单复数语法（"1 œuvres"）。

---

## 五、与实验方案的接口

Slot 1 是 `experiment-and-measurement-plan.md` 第一轮 A/B 的承载位：
- **A 版**：`You don't need its name.`（方向A，本轮推荐）
- **B 版**：`Four museums. One app.`（方向B，覆盖面）

⚠️ 零真实用户 ⇒ 该实验**现在跑不了**，gated on 正式轨道放量。
