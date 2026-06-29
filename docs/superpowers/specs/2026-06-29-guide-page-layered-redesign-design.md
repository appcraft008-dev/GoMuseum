# 讲解页改版 · 分层导览 设计 (Guide Page Layered Redesign)

**日期:** 2026-06-29
**分支:** feature/guide-layered-redesign
**设计来源:** Claude Design handoff `screens-guide-v2.jsx`（= `GoMuseum 讲解页改版.html`），方向 B「主讲 + 深度抽屉」。

## 目标

把藏品讲解页（`guide_page.dart` 的 A5 路径）从「6 个并列深度模块的信息墙」改成「分层导览」：
**默认讲解（标准导览）是绝对主角；预设问题就地展开；6 个深度模块收进底部抽屉。** 纯前端，不改后端契约。亮/暗双主题。

## 现状（要改的）

A5 路径当前自上而下：`Hero(collapsing SliverAppBar) → 墙签 → ▸作品信息 → 6模块TabBar(并列) → _AiChatShell(问题chips + 输入框)`。问题：无主角，6 模块平铺像百科。

## 契约与真实数据（2026-06-29 staging 实测）

`GET /api/v1/museums/{slug}/objects/{qid}/content` 返回字段：`qid/category/language/status/title/images/facts/tabs/suggested_questions`。
- **`default_guide` 尚未返回**（后端"即将上"，形如 `{body, audio_url}`，`audio_url` 现期为 null）。**前端必须容错其缺失。**
- `tabs`（实测 6 个）`section_code`：`overview, artist, background, analysis, significance, facts`；其中 **`overview`=「通用描述」**。部分 tab `body` 为空 → 显示「待完善」。
- `suggested_questions` 实测 **2 个**（契约 0–6 不定）→ **数量动态**，绝不写死 3。
- `tabs[].audio_url` 现期为 null（TTS 未上）。

## 核心信息架构逻辑（统一处理 default_guide 缺失）

派生规则（在 presentation 层用纯函数计算，不改 model 之外的契约）：

1. **标准导览主角 body** = `default_guide?.body` ?? `overview tab.body`（`section_code=='overview'` 那个 tab 的 body）。
   - `default_guide` 上线后优先；当前 staging 无 default_guide 时回退 overview，**今天即可正确显示**。
2. **标准导览音频** = `default_guide?.audioUrl` ?? `overview tab.audioUrl`（现期均 null → 音频条渲染为预留态）。
3. **深度抽屉 tabs** = 所有 tab **去掉被提升为主角的那个**（即去掉 overview，或 default_guide 在场时也去掉 overview）。当前 = 5 个（artist/background/analysis/significance/facts）。
4. **「深度内容（N）」按钮数字** = 抽屉 tabs 数量，**动态**。
5. 边界：
   - 若既无 default_guide 也无 overview tab → 用 `tabs.first` 当主角，其余进抽屉。
   - 若主角 body 为空但有其它 tab → 用首个 hasBody 的 tab 当主角。
   - 若 `tabs` 为空且无 default_guide → 主角区显示「待完善」，不渲染抽屉按钮。
   - `suggested_questions` 为空 → 不渲染「想深入？点一下」整段。

## 页面结构（方向 B，照设计稿）

**主页（`GuideV2Main`）**，从上到下：
- 顶栏：返回‹ · 居中「语音导览」（**去掉设计稿里的"第 3 件"**，无数据源）· 收藏★。常驻、不滚动。
- Hero 大图（高 252，**非 collapsing**，随内容滚动）：底部深色渐变 `linear-gradient(transparent 38% → rgba(0,0,0,0.66))`，叠作品中文名(serif 22)+ 英文副名(斜体)。
- 墙签行：`艺术家 · 年代 · 媒材 · 尺寸`（来自 facts，一行，下发丝线）。
- `▸ 作品信息` 折叠行（serif 粗体 + 发丝线 + 右侧弱提示）→ 复用现有 `_FactsAccordion`/`_FactsTable` 展开逻辑。
- `◆ 标准导览` 小节标题（serif、accentDeep、右侧发丝线）。
- 音频条 `GuideAudioBar`（**预留态**：圆形 play 占位 + "听讲解" 文案 + 进度线，**不显示假时长**；`audioUrl==null` 时不可点/弱化）。
- 主线讲解正文（sans 13.5 / line-height 1.95 / justify）。
- `── 想深入？点一下 ──` 分隔（两侧发丝线 + 居中弱字）。
- 预设问题 chip 竖排（按实际数量）：每个 `问题文案 ........ ›`，**点击就地展开答案**（虚线上边框 + sub 色答案），展开时 `›→⌄`。答案直接取 `suggested_questions[i].answer`（已随契约返回，无需联网）。
- 门票式按钮 `📖 深度内容（N）`（实底 ctaBg + 内虚线框 + serif），点击拉起抽屉。
- 底部常驻追问栏 `BottomAskBar`：输入框占位「问点什么…」+ 赤陶圆形麦克风🎤（静态壳，多轮对话留给后续 session B，不在本次范围）。

**底部抽屉（`GuideV2Drawer`）** —— 照设计稿：**圆角顶(18) + 柔投影**（用户已确认接受这一处偏离无圆角规则）：
- 背景：主页内容变暗（`opacity 0.36`）+ 米纸色遮罩（**亮色 `rgba(243,237,223,0.54)`；暗色须改深色遮罩**，tokenize）。
- 抽屉：抓手条 + 「深度内容」标题行（serif 17 + 右侧 close ✕）+ tab 栏（动态 tabs，选中项 serif 粗 + accent 2.5px 下划线）+ 音频条（预留）+ 正文（justify，空则「待完善」）。
- tab 可横滚（>3 个时），切换显示对应 tab 的 body/audio。

**预设问题展开态（`GuideV2QuestionOpen`）**：即主页中某个 chip 的展开状态（同一组件的 state，非独立页面）。

## 实现要点 / 范围

- **新增** `DefaultGuide` 值对象 + 在 `ObjectContent.fromJson` 防御解析 `j['default_guide']`（null 容忍，`body`/`audio_url` 均 `as String?`）。这是唯一的 model 改动（前向加法）。
- 派生逻辑（主角 body/audio、抽屉 tabs、按钮数字）抽成纯函数，便于单测。
- 全程用 `context.gm` token，不硬编码颜色 → 暗色程序生成。手动核对三处：Hero 渐变（黑色固定，双主题 OK）、抽屉遮罩（tokenize）、音频条/门票在深背景对比。
- 保留现有 `stub/generating/empty/error/loading` 状态壳。
- 复用现有组件：`GmTicketButton`（深度内容按钮可直接用）、`GmSectionHead` 风格、`_FactsAccordion`、`GmIcon`。抽屉用 `showModalBottomSheet`（isScrollControlled, 圆角顶）。
- 设计稿的假数据（"4:08"、"1:00"、"第 3 件"）一律不照搬。

## 不在本次范围

- 多轮对话 / 自由追问联网（session B，A6/A8）。追问栏保持静态壳。
- TTS 音频实际播放（`audio_url` 上线后另做；本次只留预留态 UI）。
- 后端契约改动（default_guide 由后端 session 负责上线；本前端先容错兼容）。

## 验收

- `flutter analyze` 0 issue；派生逻辑纯函数有单测。
- staging 真机：奥赛某藏品（如 Q334138）能看到 overview 当主角、抽屉 5 个深度 tab、2 个可展开问题；亮/暗各扫一遍对比度。
- default_guide 缺失（当前）与（模拟）在场两种数据都正确。
