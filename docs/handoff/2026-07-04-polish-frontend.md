# 交接（前端）：新增波兰语 pl

> 后端已加波兰语（staging）：`DEFAULT_LANGUAGES` 含 `pl`，端点 `?language=pl` 全面生效（分类标签、显示名、讲解均支持）。
> 前端只需两步——ARB 文案 + 语言选择器，与之前加 de/es/it 完全同款（PR #138-140 的模式）。

## 要做（两步）

### ① 语言选择器开放 pl
`lib/features/settings/presentation/providers/language_provider.dart`：
- `kSupportedLocales` 加 `Locale('pl')`
- `languageDisplayName` 补 pl 显示名：`Polski`

`lib/main.dart` `supportedLocales` 加 `Locale('pl')`（若用 kSupportedLocales 派生则自动）。

### ② UI 文案 ARB
`lib/l10n/app_pl.arb`：把 `app_en.arb` 全量键翻成波兰语（UI 界面文字，非藏品内容）。参照已有的 `app_de/es/it.arb` 结构。

## 验收

- 设置页可选波兰语；切 pl 后：
  - UI 文案为波兰语
  - 馆藏列表分类标签：Malarstwo / Rzeźba / Prace na papierze / Fotografia（后端已返，无需前端改）
  - 藏品标题/作者名为波兰语权威标签或翻译（后端 names 回填后生效）
  - 详情讲解为波兰语（后端 translate 后生效；未补的走懒翻译约 40s）
- `flutter analyze && flutter test` 绿；老语言不回归

## 说明

- **后端零 per-language 代码**：pl 只是配置。前端同理——加 pl 不改任何逻辑，纯文案+选择器。
- 藏品内容的 pl 覆盖率取决于后端回填进度（staging 正在跑 names+translate --langs pl）；未覆盖的件走懒翻译按需生成。

## 相关

- 契约：`docs/architecture/museum-api-contract.md`（language = DEFAULT_LANGUAGES 真相源）
- 同款先例：六语开放 PR #138-140
