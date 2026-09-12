# GoMuseum · Competitor Analysis (EN + FR, Google Play)

数据来源：2026-09-08 WebSearch 实时检索（非 Appeeky API，无法直接抓取 Play 页面详情——WebFetch 对 Play 商店页两次尝试均因内容截断失败，方法论限制记录在案）。评分/评价数量凡出现来源冲突的均并列标注，不单一采信。

## 一、既有认知 vs 本轮验证结果

| 既有认知竞品 | 本轮验证 | 结论 |
|---|---|---|
| izi.TRAVEL | ✅ 仍在架，Google Play 有独立 Beta 版并行（`travel.opas.client` + `travel.opas.client.beta`），历史评分约4星/50万+安装，但近期有用户反馈"更新后功能不可用" | 仍是重要竞品，但近期口碑有下滑迹象 |
| Bloomberg Connects | ✅ 仍在架，且**新增变量**：Paris Musées 14 家场馆（含卢浮宫、奥赛）已加入 Bloomberg Connects，40种语言 | 比既有认知更强——现在直接覆盖我们的核心馆藏，合规披露要求更高（见下） |
| GuidiGO | ✅ 仍在架（`com.guidigo`），仍是通用导览平台 | 结论不变 |
| Smartify | ✅ 是功能最接近的竞品（拍照识别），评分**来源冲突**：AppBrain 显示4.55/5（7.5千评价），另一来源显示2.8星——两个数字差异过大，不采信单一数字，标记待人工核实 | 最直接竞品，但"覆盖不了所有作品"是其已知弱点（与博物馆版权合作机制有关） |

## 二、既有资料未覆盖、本轮新发现的竞品

这批是既有 `en-US.md`/`fr-FR.md` 完全没提到的，直接命中"Louvre guide"/"Orsay guide"这类精确长尾词，比大平台更该被当作关键词层面的直接对手：

| App | Package | 定位 | 已知弱点（用户真实吐槽） |
|---|---|---|---|
| Louvre Museum Audio & Map Tour | `com.louvre.elite` | 单馆付费高端定位，"精英旅行者"话术 | 用户反馈买了 premium 仍反复弹窗要求升级、部分展项音频付费后仍播不出来 |
| Louvre Museum Audio Guide | `air.com.lvr.paris.vusiem` | 单馆音频导览，"3小时逛完卢浮宫" | 下载的导览内容会丢失、已购内容访问困难 |
| Louvre Visit, Tours & Guide | `com.tourblink.louvre` | 本地人/博主制作的步行导览，支持离线 | 未发现具体投诉，样本少 |
| Louvre Chatbot Guide | `com.wavemining.louvre` | 免费非官方 Chatbot 讲故事 | 形态是聊天机器人而非拍照识别，差异化仍成立 |
| Audio Guide Orsay Museum | `air.com.dor.paris.vusiem` | 单馆音频导览 | 与 Louvre 同发行商同模板 |
| Musée d'Orsay Travel Guide | `com.etips.orsay.travel.guide` | 免费，14+语言，行程规划型 | 通用行程规划工具改的，非专注单件展品讲解 |
| Audio Guide Musée de l'Orangerie | `air.com.orangerie.paris.vusiem` | 单馆音频导览 | 同上发行商模板 |
| Orsay Visit, Tours & Guide | `com.tourblink.museeorsay` | 步行导览，离线可用 | 与 Louvre Tourblink 同发行商 |
| Grand Palais Art Scan | Apple（Android未确认） | **官方**图像识别，但用途是展览图录伴侣App，非常设馆藏 | 场景窄（限特展图录），非全馆覆盖，威胁度低但说明"官方也在用识别技术"这个心智已被教育过 |
| ArtScan / Art Scanner with AI | 多平台，通用"识别任意画作"工具 | 不绑定任何博物馆，全球通用识别 | 无本地化博物馆内容/语音讲解，是"识别"心智的泛化竞品而非直接竞品 |

**关键发现**：至少4款"单馆音频导览"（`air.com.*.paris.vusiem` 系列）明显出自同一个发行商模板工厂，批量复制到不同博物馆——这类App 命中"Louvre guide"精确搜索词的概率很高，但功能同质化、评价里反复出现"内容访问故障"投诉。GoMuseum 的差异化机会不只是"没人做拍照识别"，还有"这批模板App口碑本身就有硬伤"——文案里可以隐含对比"没有恼人的内购解锁墙"，不点名批评竞品。

## 三、正式确认：拍照识别仍是空位，但要更精确表述

- **旧结论**（"音频导览类竞品都没有拍照识别"）在扩大竞品样本后依然成立——上表所有单馆/多馆音频导览类App均无拍照识别功能
- **需要修正的表述**：不能再说"没人做识别"，Smartify、ArtScan、Grand Palais Art Scan 都在做识别；准确表述应为——**"覆盖卢浮宫/奥赛/橘园/小皇宫这4家馆、且以拍照识别为核心交互方式的App，目前没有直接竞品"**（Smartify 覆盖范围通用但不专注这4馆且有已知覆盖缺口；Grand Palais Art Scan 场景窄）

## 四、法文市场

- 未搜到专门只做法语市场、且做拍照识别的博物馆类竞品——上表英文搜索结果里的单馆App（vusiem/tourblink系列）大概率有法语版本（同一App多语言），需 Phase 3 落实文案时逐一核实是否有独立法语listing
- Bloomberg Connects 的 Paris Musées 合作是法文市场最需要警惕的信号——40种语言、官方场馆背书，是法语本地用户最可能先接触到的替代品

## 五、Top Opportunities（沿用竞品分析技能输出格式）

1. **Quick Win：** 文案里可以强调"无内购解锁墙式故障"这个隐性对比点（多个竞品的真实差评主题），但措辞要克制、不指名道姓
2. **Keyword Gap：** `air.com.*.vusiem` 系列App 大概率已经占了"[museum name] audio guide"这类词的一部分搜索结果位——GoMuseum 应该在标题/短描述里同时覆盖"scan"/"recognition"类词，抢占它们完全没有布局的语义空间
3. **Creative Edge：** 待 Phase 3 screenshot-optimization 具体化
4. **Feature Gap：** 拍照识别 + 覆盖全部4馆常设展品，两点叠加目前无人同时占据
5. **Market Gap：** Bloomberg Connects 已经拿下 Paris Musées 官方合作，GoMuseum 不该也不能走"官方合作"叙事（`app-marketing-context.md` 已有此限制），应继续走"非官方但更懂拍照识别场景"的独立产品定位

## Sources

- [izi.TRAVEL: Audio Tour Guides - Apps on Google Play](https://play.google.com/store/apps/details?id=travel.opas.client&hl=en_US)
- [Smartify: Arts and Culture - Apps on Google Play](https://play.google.com/store/apps/details?id=com.mobgen.smartify)
- [Smartify Stats - Similarweb](https://www.similarweb.com/app/google-play/com.mobgen.smartify/statistics/)
- [Louvre Museum Audio & Map Tour - Apps on Google Play](https://play.google.com/store/apps/details?id=com.louvre.elite&hl=en)
- [Louvre Museum Audio Guide - Apps on Google Play](https://play.google.com/store/apps/details?id=air.com.lvr.paris.vusiem&hl=en_US)
- [Louvre Visit, Tours & Guide - Apps on Google Play](https://play.google.com/store/apps/details?id=com.tourblink.louvre&hl=en)
- [Louvre Chatbot Guide - Apps on Google Play](https://play.google.com/store/apps/details?id=com.wavemining.louvre&hl=en_US)
- [Audio Guide Orsay Museum - Apps on Google Play](https://play.google.com/store/apps/details?id=air.com.dor.paris.vusiem&hl=en_US)
- [Musée d'Orsay Travel Guide - Apps on Google Play](https://play.google.com/store/apps/details?id=com.etips.orsay.travel.guide)
- [Audio Guide Musée de l'Orangerie - Apps on Google Play](https://play.google.com/store/apps/details?id=air.com.orangerie.paris.vusiem&hl=en_US)
- [Orsay Visit, Tours & Guide - Apps on Google Play](https://play.google.com/store/apps/details?id=com.tourblink.museeorsay&hl=en_US)
- [Grand Palais Art Scan - App Store](https://apps.apple.com/fr/app/grand-palais-art-scan/id808208874)
- [ArtScan - Identifier Tableaux - App Store](https://apps.apple.com/us/app/artscan-identifier-tableaux/id6630371903)
- [Art Scanner with AI - Apps on Google Play](https://play.google.com/store/apps/details?id=loyd.kim.art.scanner.ai&hl=en_US)
- [GuidiGO - Apps on Google Play](https://play.google.com/store/apps/details?id=com.guidigo&hl=en_US)
- [Paris Musées is now available on Bloomberg Connects](https://www.parismusees.paris.fr/en/news/paris-musees-is-now-available-on-the-bloomberg-connects-app)
- [Connects: Arts+Culture - Apps on Google Play](https://play.google.com/store/apps/details?id=org.bloomberg.connects.docent&hl=en_US)
