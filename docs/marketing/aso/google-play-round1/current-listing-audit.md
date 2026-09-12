# GoMuseum · Pre-launch Draft Audit (Google Play, EN + FR)

**审计类型：Pre-launch Draft Audit** —— App 尚未公开发布（`play.google.com/store/apps/details?id=com.gomuseum.app` 对非白名单用户不可访问，无 URL/访问日期可记录）。本审计基于本地草稿文件，不代表已发布线上内容：

- `docs/play-assets/store-listing/en-US.md`
- `docs/play-assets/store-listing/fr-FR.md`
- `docs/play-assets/screenshots/{en-US,fr-FR}/`
- `docs/play-assets/feature-graphic/{en-US,fr-FR}.png`

Google Play（非 Apple）审计框架，字符限制/规则依据见 `android-aso` 技能：Title 30 / Short desc 80 / Full desc 4000（全部被索引），Screenshots 2–8 张/语言。以下 iOS-only 字段（Subtitle、Keyword Field）标 N/A。

## ASO Score Card（Draft，非真实线上分数）

```
Title:              8/10  ████████░░  8/30字符，品牌名干净但没打包关键词
Short description:  7/10  ███████░░░  EN 69/80、FR 76/80，接近上限，已含核心词
Full description:   6/10  ██████░░░░  EN 1227/4000（31%）、FR 1375/4000（34%），大量未用空间
Screenshots:        7/10  ███████░░░  EN/FR各12张齐备，但目录有1个命名错位文件（见下）
Feature graphic:    8/10  ████████░░  三语已定稿，1024×500，符合规格
Ratings & Reviews:  N/A         未发布，无评分数据
Keyword Rankings:   N/A         未发布，无排名数据
Icon:               待评估      未纳入本轮审计范围（用户未提供图标文件评估要求）
Conversion Signals: N/A         Play Store Experiments 需 Console 访问，本轮不连接

Overall（仅按可评估项加权）: 约 36/50 可评估分，Draft 阶段基础扎实，主要缺口在文案空间利用率
```

## Quick Wins（今天就能改）

1. **`docs/play-assets/screenshots/en-US/screenshot_FR_13.jpg` 文件命名/位置错位** ——EN 目录本身 EN_1–EN_12 已完整（12张），但多了一个法语命名的第13张混在英文目录里，大概率是误放文件，Phase 3 选图前应先确认它是否该属于 FR 目录、还是纯冗余文件待删
2. **Title 只用了 8/30 字符** ——"GoMuseum" 单独成标题，22 字符完全空置。Google Play 标题被索引且权重最高，这是本轮最大的免费流量入口，留给 Phase 3 `metadata-optimization` 处理
3. **Full description 利用率偏低**（EN 31%、FR 34%）——4000 字符全部被索引，当前只用了三分之一，有大量空间自然覆盖长尾词/场景词而不需要堆砌，留给 Phase 3

## High-Impact Changes（本周）

1. Phase 2 竞品分析完成后，重新核实"scan/识别"定位在 EN/FR 两个市场是否都缺乏竞品占位（当前只有 EN 市场的既有调研，FR 市场未验证）
2. Phase 3 输出 Title 三个候选版本时，验证含博物馆专名（Louvre/Musée d'Orsay）是否有商标/合规风险（用户 brief 第九节已提示需评估此风险）
3. 截图集从现有12张里按"前3张共同讲清楚核心价值"的原则挑选 7-8 张送审（Play 硬性上限8张/语言，现有素材数量充足，属选择题不是制作题）

## Strategic Recommendations（本月）

1. 建立 Play Store Listing Experiments 计划（Phase 4 产出），核心定位 A/B 测试排在最优先——但只有正式转入公开轨道、能连接 Console 后才能真正启动，本轮只出方案
2. 评分策略：`rating-prompt-strategy` 技能已装好，App 首次公开发布后立即用得上（In-App Review API 时机设计），本轮不需要现在执行
3. 追踪 FR 市场是否需要独立 Feature Graphic 文案（当前 FR 版是否为直译，需 Phase 3 核实并按"不得直译"的要求重新过一遍）

## 竞品对比（占位，等 Phase 2 真实数据回填）

本节故意留白，不用既有认知（`app-marketing-context.md` 里的竞品表）冒充本轮审计结论——竞品真实数据由 Phase 2 `competitor-analysis` 产出后回填本表。
