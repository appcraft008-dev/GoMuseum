# Handoff: GoMuseum — Full App UI (Warm Paper Catalogue Style)

## Overview

GoMuseum 是一款 **AI 驱动的博物馆随身导览 App**（Flutter，Android/iOS 双端）。
核心功能：拍照识别展品 → 多语言 TTS 讲解 → AI 多轮问答；按次/天付费模式。

本 handoff 包含：

- 全部主流程页面的**高保真设计稿**（HTML 原型）
- 亮色 + 暗色**设计令牌完整定义**
- 暗色主题**特殊规则**（部分元素不随主题切换）
- 各页面**布局规格 + 组件行为说明**
- **API 数据契约**（字段绑定、容错规则）

---

## 关于设计文件

`GoMuseum UI 定稿.html` 和 `GoMuseum 暗色规格.html` 是**用 HTML/React 制作的高保真设计参考原型**，
**不是**可直接部署的生产代码。

开发任务是：**在 Flutter 现有代码库中按此设计高度还原 UI**，
使用项目已有的 Flutter 组件、路由和状态管理方案，而不是直接搬运 HTML 代码。

---

## 保真度

**高保真（High-Fidelity）**：颜色、字体、间距、组件形态均为最终决策，
开发侧应**像素级还原**，包括：

- 精确颜色值（见下方 Token 表）
- 字体族、字重、字号、字间距
- 边框、圆角（本设计**无圆角**，全部直角）
- 组件内外边距

---

## 设计语言总览

**「暖纸手册 Catalogue」**风格：

- 背景像陈旧米色手工纸，内容如博物馆目录页排布
- 无圆角（border-radius: 0），所有卡片/按钮/输入框均为直角
- 主 CTA 为「门票式」：赤陶色矩形 + 虚线内框
- 章节编号体系（01/02/03）+ 菱形分隔符
- 衬线字体 Noto Serif SC 作为标题/强调，无衬线 Noto Sans SC 作为正文
- 底部导航：中央凸起的大识别按钮（圆形，超出导航栏顶部）

---

## 设计令牌

### 亮色主题（B · 暖纸手册）

```dart
// lib/theme/app_colors.dart — Light
static const bg          = Color(0xFFF3EDDF);  // 页面底色（米纸）
static const surface     = Color(0xFFFBF7EC);  // 卡片/输入框底色
static const ink         = Color(0xFF2C2316);  // 主文字
static const sub         = Color(0xFF8A7A5F);  // 次级文字
static const faint       = Color(0xFFB0A283);  // 占位/禁用
static const line        = Color(0xFFDCD2B8);  // 分隔线/边框
static const accent      = Color(0xFFA14E28);  // 强调色（Tab下划线、图标）
static const accentDeep  = Color(0xFF7E3A1C);  // 深版强调（活跃Tab文字）
static const ctaBg       = Color(0xFFA14E28);  // 主CTA背景
static const ctaInk      = Color(0xFFFBF7EC);  // 主CTA文字/图标
static const ctaDash     = Color(0x73FBF7EC);  // CTA虚线内框色（45%透明）
static const chipBg      = Color(0xFFEAE2CD);  // chip/tag背景
```

### 暗色主题（BD · 暖纸手册夜版）

```dart
// lib/theme/app_colors.dart — Dark
static const bg          = Color(0xFF201A12);  // 深褐纸底
static const surface     = Color(0xFF2A2218);
static const ink         = Color(0xFFEFE6D2);
static const sub         = Color(0xFFA89878);
static const faint       = Color(0xFF6E614C);
static const line        = Color(0xFF3A3022);
static const accent      = Color(0xFFD08050);  // 提亮赤陶
static const accentDeep  = Color(0xFFE09668);
static const ctaBg       = Color(0xFFC26A3A);
static const ctaInk      = Color(0xFF241A0F);
static const ctaDash     = Color(0x73241A0F);  // 45%透明
static const chipBg      = Color(0xFF332A1D);
```

### Flutter ColorScheme 映射

| 设计 Token   | ColorScheme 字段                   |
| ------------ | ---------------------------------- |
| bg           | ColorScheme.surface                |
| surface      | ColorScheme.surfaceContainerLowest |
| ink          | ColorScheme.onSurface              |
| accent/ctaBg | ColorScheme.primary                |
| ctaInk       | ColorScheme.onPrimary              |
| line         | ColorScheme.outlineVariant         |
| sub/faint    | ColorScheme.onSurfaceVariant       |
| chipBg       | ColorScheme.surfaceContainerHigh   |

### 字体

```dart
// 标题/强调
fontFamily: 'NotoSerifSC', fontWeight: FontWeight.w700
// 正文/UI
fontFamily: 'NotoSansSC', fontWeight: FontWeight.w400
```

---

## 特殊规则（不随主题切换）

| 场景             | 规则                                                                                                  |
| ---------------- | ----------------------------------------------------------------------------------------------------- |
| 取景器背景       | 硬编码 `#0F0C09`，与主题无关；控制条下半区用 `t.bg`                                                   |
| Hero大图渐变遮罩 | 始终 `LinearGradient(transparent→rgba(0,0,0,0.68))`                                                   |
| Hero标题文字     | 始终 `#F6F1E4`（白），不跟主题切换                                                                    |
| Hero版权署名     | 始终 `rgba(246,241,228,0.38)`                                                                         |
| 识别结果弹出遮罩 | 亮色：`rgba(44,35,22,0.32)` · 暗色：`rgba(0,0,0,0.5)`                                                 |
| 中央识别按钮阴影 | 亮色：`BoxShadow(rgba(44,35,22,0.28), blur:16, offset:y6)` · 暗色：`BoxShadow(rgba(0,0,0,0.45), ...)` |

---

## 页面清单与规格

### 1. 登录页 `LoginScreen`

**入口**：冷启动 / 未登录时

| 区域                 | 规格                                                                                  |
| -------------------- | ------------------------------------------------------------------------------------- |
| 品牌区 paddingTop    | 52dp                                                                                  |
| GOMUSEUM 字体        | NotoSerifSC 27sp w900，letterSpacing 9sp                                              |
| 菱形分隔             | 50dp宽，赤陶色◆，两侧1px线                                                            |
| 副标题               | 13sp letterSpacing 4sp，sub色                                                         |
| 输入框               | 高58dp，surface底，1px line边框，无圆角；placeholder 15.5sp faint色                   |
| 登录CTA              | 门票式：ctaBg底，7dp内边距，1px ctaDash虚线内框，ticket图标+「登　录」letterSpacing 7 |
| 「还没有账号？注册」 | 14.5sp accent色，居中文字按钮                                                         |
| 分隔线               | 两侧1px line，中间「或使用以下方式登录」12.5sp sub色                                  |
| Google/Apple按钮     | 高58dp，surface底，1px line边框，NotoSerifSC 15.5sp                                   |
| 「或」分隔           | 同上，文字更短                                                                        |
| 游客登录             | 高58dp，chipBg底，1px line边框，NotoSerifSC 16.5sp w700                               |

---

### 2. 首页 `HomeScreen`

**导航 Tab**：首页

| 区域             | 规格                                                                                             |
| ---------------- | ------------------------------------------------------------------------------------------------ |
| 顶栏左：城市选择 | pin图标(16dp accent) + 城市名NotoSerifSC 16sp w700 + chevDown图标；tap展开城市选择下拉           |
| 顶栏中-左：天气  | cloudSun图标 + 气温NotoSerifSC 16sp w700 + 天气描述10sp sub；紧跟城市，细竖线分隔                |
| 顶栏右：邮件     | mail图标(20dp) + 红点未读标记(6dp accent)                                                        |
| 刊头             | GOMUSEUM 13sp letterSpacing 7，菱形分隔，副标11sp letterSpacing 3                                |
| 主CTA            | 门票式（同登录页风格），camera图标+「拍照识别讲解」，下方「免费X次·升级」12sp                    |
| 博物馆横滑卡片   | 水平ScrollView，卡片宽268dp；surface底+1px line；内含缩略图(132dp高)+馆名+状态+距离+馆藏缩略图行 |
| 指示点           | 激活16×4dp赤陶圆角，非激活4×4dp faint                                                            |
| 底部导航         | 见「底部导航」章节                                                                               |

**城市下拉面板**（点城市名弹出）：

- 左锚点，宽约屏幕2/3，surface底，6dp圆角，阴影
- 顶部搜索框44dp + 「使用我的当前位置」link
- 城市列表：城市名NotoSerifSC + 英文名11sp faint + 博物馆数量；当前城市chipBg底 + 右侧√
- 背景遮罩：rgba(44,35,22,0.32)，点遮罩关闭

---

### 3. 取景拍照页 `CaptureScreen`

**入口**：首页CTA tap / 底部导航中央识别按钮

| 区域             | 规格                                                              |
| ---------------- | ----------------------------------------------------------------- |
| 取景器区域       | 相机预览全屏；顶部渐变遮罩(顶50%→透明)；底部渐变遮罩(透明→65%)    |
| 顶栏按钮         | × 关闭 + 「识别画作」胶囊(半透明黑底) + 闪光灯；各38dp圆形按钮    |
| 四角参考框       | 34×34dp，2.5px白线，四个角L形                                     |
| 中心提示         | 「将画作完整置于取景框内」，胶囊半透明黑底12.5sp白字              |
| 控制条（暖纸区） | t.bg底                                                            |
| 最近图库横排     | 「最近图库」标签+「全部相册→」；52×52dp缩略图，1px line边框       |
| 快门行           | 图库按钮(46×46dp方形) + 快门(74dp圆形ctaBg+4dp bg描边) + 搜索按钮 |

---

### 4. 候选确认页 `RecognitionResultScreen`

**入口**：拍照/选图完成后

| 区域             | 规格                                                                  |
| ---------------- | --------------------------------------------------------------------- |
| 上半：取景器残像 | 相机预览图层（淡出态）                                                |
| 底部弹出面板     | bg底，18px 18px 0 0圆角（注意：本设计唯一有圆角的场景，标识系统界面） |
| 拖动把手         | 36×4dp，line色，居中                                                  |
| 主候选卡         | 1.5px accent边框，flex行：缩略图60×60+标题+置信度%；NotoSerifSC       |
| 其他候选         | 普通列表行，40×40缩略图，置信度用faint小字                            |
| 确认CTA          | 门票式，headphones图标+「确认，开始讲解」                             |
| 底部文字链       | 「都不是？搜索作品名或展签编号 →」accent色居中                        |

---

### 5. 讲解页 `GuideDetailScreen`

**入口**：确认候选后 / 足迹列表tap

**布局**：顶栏(固定) + 可滚动区(Hero→内容) + AI问答条(固定底部)

| 区域            | 规格                                                                      |
| --------------- | ------------------------------------------------------------------------- |
| 顶栏            | ← + 「语音导览·第N件」11sp letterSpacing3 + ★收藏                         |
| Hero大图        | 全出血，高286dp（≈屏幕1/3），objectFit:cover；底部渐变→标题叠加           |
| Hero标题叠加    | NotoSerifSC 22sp w700 白色，原文名12sp italic；右上角多图指示点           |
| Hero版权署名    | 右下角9sp rgba(246,241,228,0.38)                                          |
| 流式墙签        | 「作者·年代·媒材·尺寸」12.5sp sub色，1行；borderBottom 1px line           |
| ▸作品信息手风琴 | 默认折叠；展开显示6行表格(馆藏编号/现藏地/来源/展览史/签名/文献)          |
| Tab栏           | 介绍/作者/背景/故事，NotoSerifSC 12.5sp；活跃2.5px accent下划线           |
| TTS播放器       | 44dp圆形ctaBg播放按钮 + 进度条(accent色) + 时间 + 倍速按钮                |
| 讲解正文        | 13.5sp lineHeight 1.9，justify对齐；「看点」分隔行(serif w700 accentDeep) |
| AI问答底栏      | 推荐chips + 输入框 + 🎤；固定底部，borderTop 1px line                     |

**Hero折叠行为（滚动时）**：

- 滚出视口后顶栏中央显示作品名（NotoSerifSC 14.5sp w700）
- 参考：Flutter SliverAppBar + CollapsingToolbar

---

### 6. AI聊天面板 `AIChatBottomSheet`

**入口**：讲解页底栏 — 点chip或点输入框

| 区域          | 规格                                                              |
| ------------- | ----------------------------------------------------------------- |
| 面板高度      | 约屏幕高度78%，从底部弹起（BottomSheet/DraggableScrollableSheet） |
| 拖动把手      | 36×4dp，line色                                                    |
| 顶部锚点      | 作品缩略图42×42dp(装裱框) + 标题+作者年代 + ↓收回按钮34×34dp      |
| 用户气泡      | 右对齐，maxWidth 84%，ctaBg底，ctaInk文字，无圆角                 |
| 助手气泡      | 左对齐，maxWidth 84%，surface底，1px line边框，ink文字            |
| 助手消息底部  | 🔊朗读按钮(accent色边框+文字) + 「来源：xxx」10.5sp faint         |
| 流式指示      | 助手气泡内显示「···」letterSpacing4，faint色，17sp                |
| 后续推荐chips | 上方「继续问」9.5sp faint标签 + chip行（chipBg底，1px line边框）  |
| 底部输入条    | 输入框flex1 + 🎤方形46×46dp + 发送↑方形44×44dp ctaBg底            |

**行为**：

- 点收回/下划 → 关闭面板，停止TTS朗读
- 离开页面 → 停止TTS朗读
- 流式生成：POST /content/ask {qid, language, messages[]}（SSE流式）
- 朗读：POST /tts/generate → 播放音频

---

### 7. 探索页 `ExploreScreen`

**导航 Tab**：探索

| 区域          | 规格                                                     |
| ------------- | -------------------------------------------------------- |
| 刊头          | 「探 索」NotoSerifSC 21sp w700 letterSpacing4 + 菱形分隔 |
| 搜索框        | 高46dp，surface底，1px line；search图标+placeholder      |
| 城市筛选chips | 激活：ctaBg底；非激活：transparent + line边框；12.5sp    |
| 区块标题行    | 「01 城市名 ─── 数量→」样式                              |
| 博物馆主卡    | 同首页横滑卡片，但纵向布局，全宽                         |
| 博物馆列表行  | 高58dp，编号+名称+元信息+chevR                           |

---

### 8. 馆藏列表页 `CollectionListScreen`

**入口**：探索页 tap 博物馆

| 区域        | 规格                                                                          |
| ----------- | ----------------------------------------------------------------------------- |
| 顶栏        | ← + 馆名(NotoSerifSC 16sp) + 藏品数(10sp sub) + search图标                    |
| 分类Tab横滑 | 数据：GET /museums/{slug} → categories:[{code,label,count}]                   |
|             | Tab格式：类别名(NotoSerifSC 13sp) + 数量(9.5sp faint)；活跃2.5px accent下划线 |
| 2列网格     | gap 12dp，每卡：surface底+1px line；6dp内padding缩略图+文字区                 |
| 卡片缩略图  | 全宽，高116dp，objectFit:cover；缺失时显示photo占位图                         |
| 卡片文字区  | 标题NotoSerifSC 12.5sp w600 maxLine2；作者10.5sp sub                          |
| 无限滚动    | GET /museums/{slug}/objects?category=X&sort=popularity&limit=50&offset=N      |
| 底部加载态  | 旋转圈(22dp，borderTopColor:accent) + 「正在加载·已显示X/Y」                  |
| 底部完成态  | 菱形分隔 + 「已全部加载·共N件」11.5sp faint                                   |
| 空字段容错  | thumbnail缺失→占位图；title缺失→「未命名」；禁止 null 强转崩溃                |

---

### 9. 足迹页 `FootprintScreen`

**导航 Tab**：足迹

| 区域   | 规格                                                                           |
| ------ | ------------------------------------------------------------------------------ |
| 刊头   | 「足 迹」+ 菱形 + 统计数字(城市/博物馆/作品)                                   |
| 分组   | 按博物馆分组，编号体系(01/02/03)                                               |
| 列表行 | 46×46dp缩略图 + 作品名(NotoSerifSC 14.5sp) + 时间+状态(11.5sp sub) + ★收藏状态 |

---

### 10. 设置页 `SettingsScreen`

**导航 Tab**：设置

| 区域         | 规格                                                                         |
| ------------ | ---------------------------------------------------------------------------- |
| 免费额度卡   | 门票式内框(同登录CTA风格)；进度条3dp高，accent底色                           |
| 升级按钮     | ctaBg底，NotoSerifSC letterSpacing 2                                         |
| 设置行       | 高48dp；图标(19dp sub) + 标题(14sp) + 值/toggle                              |
| **外观切换** | 分段控件：「浅色/深色/跟随系统」；激活态ctaBg底ctaInk文字；非激活transparent |
| Toggle开关   | 宽40dp高23dp，激活accent底，圆形滑块surface色                                |

---

## 底部导航（全局）

```
[首页] [探索] [●识别●] [足迹] [设置]
         ↑中央凸起圆形按钮
```

| 规格         | 值                                                           |
| ------------ | ------------------------------------------------------------ |
| 导航条高度   | 68dp                                                         |
| 中央按钮     | 60dp圆形，ctaBg底，camera图标26dp ctaInk；凸出导航栏上方26dp |
| 中央按钮描边 | 4px bg色环，BoxShadow(rgba(44,35,22,0.28))                   |
| Tab激活色    | accentDeep；非激活faint                                      |
| Tab标签      | 10.5sp letterSpacing 1                                       |

---

## 数据接口摘要

```
# 博物馆列表
GET /api/v1/museums?city={city}&lat={lat}&lng={lng}

# 博物馆详情（含分类）
GET /api/v1/museums/{slug}
→ { name, categories:[{code,label,count}], ... }

# 藏品列表（无限滚动）
GET /api/v1/museums/{slug}/objects?category={code}&sort=popularity&limit=50&offset={n}
→ { items:[{id,thumbnail,title,author}], total, limit, offset }

# 藏品讲解内容
GET /api/v1/museums/{slug}/objects/{qid}/content
→ { title, images:[{url,credit}], facts:{...}, tabs:[{id,text}],
    suggested_questions:[string] }

# AI 多轮问答（SSE流式）
POST /api/v1/content/ask
body: { qid, language, messages:[{role,content}] }

# TTS 生成
POST /api/v1/tts/generate
body: { text, language, voice }
→ { audio_url }
```

---

## 暗色主题实现说明

1. 亮色页面已全部设计（见画布）
2. **暗色主题通过 token 自动切换**——所有颜色引用 `Theme.of(context).colorScheme.*`，无硬编码色值
3. **有代表性暗色参考画板**的页面（直接可对照）：登录页、首页、识别页、讲解页、AI聊天面板
4. 其余页面依 token 套用，对照「GoMuseum 暗色规格.html」中的特殊规则处理例外情况
5. **暗色 QA 优先级**：讲解页Hero对比度 > 取景器交界 > 设置分段控件 > 其余

---

## 文件清单

| 文件                     | 说明                                       |
| ------------------------ | ------------------------------------------ |
| `GoMuseum UI 定稿.html`  | 全部页面高保真设计画布（可在浏览器中预览） |
| `GoMuseum 暗色规格.html` | 暗色 token 对照表 + 特殊规则 + Flutter映射 |
| `gm-shared.jsx`          | 设计令牌源码（GM_THEMES.B / BD）           |
| `screens-final.jsx`      | 各页面组件源码（含布局逻辑参考）           |
| `assets/art/`            | 设计用测试图片（梵高公有领域名画）         |

---

_GoMuseum Design Handoff · 2026 · 版本 1.0_
