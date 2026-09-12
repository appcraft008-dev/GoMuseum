# GoMuseum · Google Play ASO Round 1 — Executive Summary

生成于 2026-09-08。范围：Google Play only，英文+法文市场。完整产出见同目录其余9个文件。**所有文案/截图/实验方案均为草案，交付审核，未做任何线上/代码改动。**

## 最重要的5项发现

1. **拍照识别仍是空位，但表述要更精确**——扩大竞品样本后（新发现至少8款既有资料没覆盖的竞品），"没人做识别"这个说法不再成立（ArtScan、Art Identifier、Smartify、Grand Palais Art Scan 都在做）。真正成立的判断是：**覆盖卢浮宫/奥赛/橘园/小皇宫这4家馆、且以拍照识别为核心交互方式的App，目前没有直接竞品**。
2. **发现一批既有资料完全没提到的直接竞品**——至少4款"单馆音频导览"App（`air.com.*.paris.vusiem`系列）出自同一发行商模板，精确命中"Louvre guide"/"Orsay guide"这类高意图搜索词，且用户真实差评集中在"内购解锁墙故障、押金归还问题"，这是本轮找到的可用差异化叙事素材。
3. **Bloomberg Connects 已拿下 Paris Musées 官方合作**（含卢浮宫、奥赛，40种语言）——这是既有资料未追踪到的新竞争信号，直接提高了"不得暗示官方合作"这条限制的重要性，法文市场尤其敏感。
4. **截图素材有两个真实缺陷，上传前必须处理**：①首页截图显示"999992 free scans left"测试占位数据，需用真实数据（5次）重新截图；②Mona Lisa详情页截图里有"Ask anything..."自由输入框，暗示实时AI对话，与产品实际状态（`/chat/ask`已下线返回503）冲突，直接用会构成"宣传不存在的功能"。
5. **既有商店文案的语言数量写错了**——写的是"9 languages"，代码实际支持10种（简繁中文是两个独立选项），本轮已在新文案里修正；同一问题也存在于刚发布的落地页（`deployment/website/`），需要一并修正（不在本轮范围内，记录供参考）。

## 补充决策（2026-09-13，用户拍板）："AI"不作为卖点

用户明确倾向：**标题/简短描述/完整描述均不用"AI"（法文对应"IA"）这个词做卖点**。理由与本轮竞品研究结论一致——"AI"在2026年已趋同质化、不再是差异化信号，且可能招来用户对AI生成内容质量的天然警惕；改用"grounded / fact-checked / never invented"这组更具体的信任表述，比空泛提"AI"更有说服力，也更贴合本项目"正确性靠构造不靠宣传"的产品原则。据此，下方英/法文最终推荐已改为**不含AI/IA字样的版本**（原含AI字样的候选已在 `metadata-final-{en-US,fr-FR}.md` 中标记为已否决，保留存档供参考），同期已同步修正落地页（`deployment/website/`）标题标签与文案中的AI/IA提法。

## 英文市场最终推荐

- **Title:** `GoMuseum: Scan Louvre Art`（25/30字符）
- **Short description:** `Scan artwork at the Louvre & Orsay for an instant museum audio guide.`（69/80字符，=既有稿，本轮验证后确认无需改动）
- **Full description:** 见 `metadata-final-en-US.md`（1816/4000字符，45%利用率，较既有稿提升定位精度+竞品差异化叙事+官方合作撇清声明，且不含AI字样）
- 详见 `metadata-final-en-US.md`（含2个已否决的AI版本存档+关键词覆盖矩阵）

## 法文市场最终推荐

- **Titre:** `GoMuseum : Scannez le Louvre`（28/30字符）
- **Description courte:** `Photographiez une œuvre au Louvre ou à Orsay pour un guide audio instantané.`（76/80字符，=既有稿，本轮验证后确认无需改动）
- **Description complète:** 见 `metadata-final-fr-FR.md`（1971/4000字符，不含IA字样）
- ⚠️ "guide audio"（两词）vs "audioguide"（一词）本轮未裁定，建议作为 Phase 4 A/B测试候选，而非拍脑袋二选一
- 详见 `metadata-final-fr-FR.md`

## 方向A是否得到验证

**部分验证，但需要修正表述**（见上方"最重要的5项发现"第1条）。原始判断"竞品都做audio guide，没人做识别"过于宽泛，本轮用真实竞品数据把它收窄到一个仍然成立、但更具体的空位：**识别 + 这4家特定巴黎博物馆**的组合。这个收窄后的结论在英文和法文市场看下来都成立（法文市场同样没找到"识别+这4馆"的直接竞品），但法文市场竞品覆盖没有像英文那样逐个验证到评分/评论细节，属于中等置信度而非高置信度结论。

## 需要修正的已有结论

1. 语言数量 9→10（`en-US.md`/`fr-FR.md`/落地页三处都受影响，本轮只改了本目录内的新文案，原始三处文件未动，需要用户决定是否同步）
2. "音频导览类竞品都没有识别功能"→收窄为"覆盖这4家馆的识别类App没有直接竞品"（见上）
3. `app-marketing-context.md`记录的既有竞品认知（izi.TRAVEL评分下滑迹象、Smartify评分来源冲突）需要标记为"待人工核实"而非既定事实

## 可以立即实施的项目（Quick Wins）

1. 用真实免费次数（5次）重新截取首页截图，替换含占位数据的版本
2. 排查`screenshot_EN_7.jpg`里"Ask anything"输入框是产品UI残留还是仍在渲染中的旧组件——这是产品侧待办，不是ASO文案能解决的，但会直接影响能否合规上传截图
3. Title从8/30字符利用率提升到25-28/30——`metadata-final-{en-US,fr-FR}.md`已给出可直接采用的3个候选版本
4. `docs/play-assets/screenshots/en-US/screenshot_FR_13.jpg`文件位置/命名错位，需要确认它该删除还是移到`fr-FR/`目录

## 仍需真实数据验证的假设

1. **本轮所有关键词的Volume/Difficulty全部是方向性判断**，没有Appeeky等付费数据源支撑（`keyword-research-{en-US,fr-FR}.md`已逐项标注），正式接入真实数据源后需要整体复核
2. Smartify的Play评分（4.55 vs 2.8两个来源冲突）未解决，需人工直接打开Play页面核实
3. FR市场的`vusiem`/`tourblink`系列竞品是否真的有独立法语listing，本轮WebFetch抓取Play页面两次尝试均因内容截断失败，未能验证（方法论限制，非结论）
4. FR/CN截图目录（各12张）本轮未逐张核实是否与EN截图一一对应，`creative-brief-en-fr.md`的排序建议默认对应但未验证

## 推荐的下一步行动顺序

1. 产品侧先确认并处理两个截图缺陷（占位数据、Ask anything输入框）——这是唯一真正阻塞视觉素材上传的问题
2. 用户审核本轮全部10份文档，对文案/截图顺序/实验方案给出修改意见
3. 待 Play 正式转入公开轨道、能连接 Console 后，才能真正启动 Phase 4 的核心定位A/B测试——本轮方案是提前准备，不是可以现在执行的任务
4. 法文市场的竞品验证（尤其`vusiem`系列是否有独立FR listing）建议作为下一轮的第一项，置信度目前偏低

## 文件清单

- `app-marketing-context.md`
- `current-listing-audit.md`
- `competitor-analysis-en-fr.md`
- `keyword-research-en-US.md`
- `keyword-research-fr-FR.md`
- `metadata-final-en-US.md`
- `metadata-final-fr-FR.md`
- `creative-brief-en-fr.md`
- `experiment-and-measurement-plan.md`
- `executive-summary.md`（本文件）
