# GoMuseum · Creative Brief — Feature Graphic + Screenshots (EN + FR)

本节基于**实际查看**了 `docs/play-assets/screenshots/en-US/` 全部12张截图（非猜测），FR/CN 两套按文件数对称（各12张）推定内容对应，但未逐张核实——Phase 3 落地前建议抽查确认 FR 截图确实对应同一批界面。

## ⚠️ 上传前必须处理的两个真实问题

1. **`screenshot_EN_2.jpg`（首页）显示"999992 free scans left"** —— 明显是测试占位数据，真实免费额度是5次（`app-marketing-context.md`已确认）。这张是本轮设计里的 Slot 1 首选素材，**必须用真实数据重新截图后才能用**，现在这张不能直接上传
2. **`screenshot_EN_7.jpg`（Mona Lisa 详情页）底部有"Ask anything..."输入框+麦克风图标** —— 这个UI元素强烈暗示"自由提问/实时对话"，与 `app-marketing-context.md` 的明确限制冲突（该功能已下线，`/chat/ask` 返回503）。**不能直接用这张做商店截图**，除非产品侧先把这个输入框从界面移除/禁用（这是一个产品侧待办，不是这轮 ASO 能处理的，但必须记录下来）——这张如果就这样传到商店，本身就是"宣传不存在的功能"，会撞上 Play 商店审核的功能真实性要求

## 现有12张素材的构成（EN，实际查看结果）

| 文件 | 内容 | 评估 |
|---|---|---|
| EN_1 | 登录页（Email/密码/Google/Apple/Guest） | 不适合做商店截图（登录页转化力弱，是行业公认的反模式） |
| EN_2 | 首页：标语+Snap CTA+附近博物馆 | 最强 Hook 候选，但含占位数据bug（见上） |
| EN_3 | Explore：搜索+4馆列表（Louvre/Orangerie/Orsay/Petit Palais） | 很好的"一个App四家馆"证明素材 |
| EN_4 | 博物馆详情页封面（历史介绍长文本） | 文字密度高，视觉冲击弱，备选 |
| EN_5 | 藏品列表（Mona Lisa/Venus de Milo/Liberty Leading the People等） | 很好的"海量知名作品"证明素材 |
| EN_6 | 拍照识别进行中（对着Mona Lisa扫描） | **核心机制展示**，本轮最重要的差异化时刻 |
| EN_7 | Mona Lisa结果页（讲解+"Ask anything"输入框） | 内容好但有上述问题2，需处理后才能用 |
| EN_8–EN_12 | "In depth"子标签页5连拍（Artist/Background/Analysis/Significance/Facts，同一界面切了5个tab） | **5张高度重复**，只是切换了选中的tab，文字密度都很高——不该占5个宝贵的截图位，最多保留1张作为"内容够深"的证明 |

**关键发现**：12张素材里有5张（EN_8–12）是同一界面的重复变体，实际有差异化价值的素材只有约7张——这正好卡在 Play 的8张上限附近，说明"前7张"这个思路是对的，但**不是从12张里随便挑7张，是要先砍掉5张重复的再排序**。

## Feature Graphic（1024×500px）

已有三语定稿（`docs/play-assets/feature-graphic/`），核对内容脚本（`feature-graphic/README.md`）：品牌图标+"GOMUSEUM"+"SCAN · LISTEN · EXPLORE"标语，暖纸色系背景。

- **核心传播信息**：不用改——已经精准对应本轮验证的定位（scan优先于纯audio guide）
- **禁止出现的误导信息**：不得加入任何暗示官方合作或实时AI对话的文字/图形元素
- **法语版**：确认标语翻译是否为"SCAN · ÉCOUTEZ · EXPLOREZ"或等效表达，需与 Phase 3 metadata 里"Scannez"的动词形式保持术语一致（避免同一产品在不同素材里动词变位不统一）

## 前7张商店截图排序建议（EN，基于实际素材）

| 序号 | 素材 | 营销目标 | 建议标题文案 | 备注 |
|---|---|---|---|---|
| 1 | EN_2改（首页，修复免费次数bug后重截） | Hook——一句话说清楚是什么 | "Scan any artwork. Hear its story." | 必须先修复占位数据 |
| 2 | EN_6（扫描进行中） | 核心机制可视化，本轮差异化最强的一帧 | "Point your camera — GoMuseum does the rest" | 直接对应"scan"关键词定位 |
| 3 | EN_7改（结果页，移除/裁掉"Ask anything"输入框） | 展示讲解内容质量 | "Grounded, fact-checked — never invented" | 需产品侧先处理输入框问题 |
| 4 | EN_3（Explore四馆列表） | 覆盖范围证明 | "Louvre, Orsay, Orangerie, Petit Palais — one app" | 直接呼应"4家馆"卖点 |
| 5 | EN_5（藏品列表） | 内容深度/广度证明 | "Thousands of works, always findable" | 用真实作品名增强可信度 |
| 6 | EN_8~12选1（建议用Analysis或Significance其中一张） | "内容够深"的信任信号 | "Go as deep as you want" | 只留1张，别5张全上 |
| 7 | **待补素材**：Paris City Pass / 定价页 | 转化前最后一击，说明付费模式清晰不套路 | "One pass, unlimited — no hidden catches" | **现有12张里没找到这张**，需要产品侧补充截图（Phase 3 未能覆盖，记录为缺口） |

第8个备用位（Play允许最多8张）：可考虑加一张语言选择器截图，呼应"10种语言"卖点，但优先级低于以上7张。

## FR 版处理建议

- 结构与顺序原则上照搬上表，前提是 FR 截图目录里对应界面的法语文案已就位且无同样的bug（占位数据、"Ask anything"输入框大概率是同一份代码渲染的，同样需要检查）
- 本轮未逐张核实 FR/CN 目录，这是一个已知方法论缺口，记录在 `executive-summary.md`

## 与 Phase 4 的接口

Slot 1（Hook screenshot）是 `experiment-and-measurement-plan.md` 里"核心定位A/B测试"最适合承载的位置——同一 Slot 1 位置可以测试"Scan any artwork"（方向A）vs 更泛化的"Explore 4 Paris museums"（方向B）两个版本。
