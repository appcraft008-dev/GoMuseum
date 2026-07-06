# 交接（前端）：新增三种非拉丁语言 ja / ko / zh-hant

> 后端已全部就绪（staging）：`DEFAULT_LANGUAGES` 已含 `ja`、`ko`、`zh-hant`。
> `?language=ja|ko|zh-hant` 对分类标签、显示名、讲解/问答**全面生效**（实测三语翻译质量六检查点全绿）。
> 前端加 ja/ko 与之前加波兰语**完全同款**；**zh-hant 有 4 个必须处理的陷阱**（见下），否则会把繁体请求发成简体。

## 语言与展示名

| API code | Flutter locale | 展示名 |
|---|---|---|
| `ja` | `Locale('ja')` | 日本語 |
| `ko` | `Locale('ko')` | 한국어 |
| `zh-hant` | `Locale.fromSubtags(languageCode:'zh', scriptCode:'Hant')` | 繁體中文 |

## A. ja / ko —— 标准三步（同波兰语 #138-140 / polish handoff）

1. `kSupportedLocales` 加 `Locale('ja')`、`Locale('ko')`。
2. `_kLanguageNames` 加 `'ja': '日本語'`、`'ko': '한국어'`。
3. ARB 文案：`app_ja.arb`、`app_ko.arb`（全量键翻译，参照 `app_de.arb` 结构）。

ja/ko 的 API 参数走现有 `locale.languageCode`（='ja'/'ko'）即可，无特殊处理。

## B. zh-hant —— 4 个陷阱（务必全处理）

现状：全 App 的 API 语言参数来自 `ref.read(languageProvider).languageCode`（约 8 处：catalog_providers、guide_page、camera_page、museum_page、explore_page 等）。繁体中文会踩以下坑：

### 陷阱 1：locale 表示法
繁体中文的 Flutter locale 必须是 `Locale.fromSubtags(languageCode:'zh', scriptCode:'Hant')`（不是 `Locale('zh-hant')`——那样 Flutter 本地化/ARB 解析不认）。ARB 文件名 `app_zh_Hant.arb`。

### 陷阱 2（最关键）：API 参数必须发 `zh-hant`，不能发 `zh`
上面那个 locale 的 `.languageCode` 是 **`'zh'`**——直接用它当 API 参数会请求到**简体**内容（后端 `zh` 和 `zh-hant` 是两套）。**必须引入映射函数**并替换所有 API-参数取值处：
```dart
String apiLanguage(Locale l) =>
    (l.languageCode == 'zh' && l.scriptCode == 'Hant') ? 'zh-hant' : l.languageCode;
```
把所有 `ref.read/watch(languageProvider).languageCode`（作 API 参数用的）换成 `apiLanguage(ref.read(languageProvider))`。

### 陷阱 3：持久化 round-trip 丢 scriptCode
`language_provider.dart` 现在 `setLanguage` 存 `locale.languageCode`、`_loadLanguage` 用 `Locale(code)` 还原——繁体会丢 `Hant`。改成存/读**完整 language tag**（`locale.toLanguageTag()` → 存 `'zh-Hant'`；读时解析回 `Locale.fromSubtags`）。建 `_localeFromTag(String)` / `_tagOf(Locale)` 两个小工具。

### 陷阱 4：展示名 map 键冲突
`_kLanguageNames` 以 `languageCode` 为键——`zh`（简体中文）和 `zh-Hant`（繁體中文）都是 `'zh'`，会撞。展示名查找改为按**完整 tag**（或加 scriptCode 分支）：`zh-Hant → 繁體中文`、`zh → 简体中文`。

## C. 顺带：CJK 排版
`gm_theme_x.dart` 的 `isCjk => languageCode == 'zh'` 只认简中。**ja/ko/zh-hant 都应算 CJK**（字体/断行/行高）。改成 `{'zh','ja','ko'}.contains(languageCode)`（zh-Hant 的 languageCode 也是 'zh'，天然覆盖）。

## 验收

- 设置页可选 日本語 / 한국어 / 繁體中文。
- 切 **繁體中文** 后（重点验陷阱 2）：
  - 馆藏列表标题为**繁体**（庫爾貝《世界的起源》《煎餅磨坊的舞會》），**不是简体**——若显示简体=API 发了 `zh` 没发 `zh-hant`。
  - 分类标签：繪畫 / 雕塑 / 攝影。
  - 详情讲解/问答为繁体。
- 切 日本語：絵画/彫刻、標題与讲解为日语（エドゥアール・マネ 等）。
- 切 한국어：회화/조각、韩语（세상의 기원、에두아르 마네）。
- `flutter analyze && flutter test` 绿；简体中文/其他语言不回归。

## 相关
- 契约：`docs/architecture/museum-api-contract.md`（language=DEFAULT_LANGUAGES 真相源）
- 翻译质量清单：`docs/i18n-translation-quality-checklist.md`（含字形变体/非拉丁分类）
- 同款先例：波兰语 `docs/handoff/2026-07-04-polish-frontend.md`
