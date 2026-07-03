# 交接：App 开放 6 语言（de/es/it 加入语言选择器）

> 后端已先行（场景1）：内容生成六语（en/fr/de/es/it/zh），staging 已有真实 de/es/it 数据可测。
> 前端升级配合开放选项。**契约零变化**——`language` 参数本来就收任意语言码。

## 现状（基础已埋好）

- ✅ `lib/l10n/app_{de,es,it}.arb` 六语 UI 文案齐全
- ✅ `lib/main.dart` `supportedLocales` 已列全 6 种
- ❌ **唯一卡点**：`lib/features/settings/presentation/providers/language_provider.dart`
  的 `kSupportedLocales` 只有 zh/en/fr → 设置页选不到 de/es/it

## 要做

1. `kSupportedLocales` 加 `Locale('de'), Locale('es'), Locale('it')`；
   `languageDisplayName` 补三语显示名（Deutsch / Español / Italiano）。
2. 确认列表/详情请求把 locale 透传到 API `language` 参数（应已是通用逻辑，验一下即可）。
3. 排版：拉丁语正文行高分档已做（#113），de 词长易折行，抽查设置页/标题不截断。
4. 手测 staging（`staging-api.gomuseum.app`，staging flavor 包名 `com.gomuseum.app.staging`）：
   - 列表页 de/es/it：标题/作者名应为该语权威标签或翻译（显示名回填已全量）
   - 详情页测试件：`Q3358957`（奥维里）六语讲解全有
   - **注意**：存量老件（早期 243 件）只生成过 zh/en/fr 讲解，de/es/it 视图会显"待完善"
     ——这是预期（empty 容错已有），后端"补语种"增量命令在后端 backlog 里。

## 验收

- 设置页可选 6 语；切 de/es/it 后 UI 文案 + 列表显示名 + Q3358957 详情内容均为该语言。
- `flutter analyze && flutter test` 绿；老 3 语行为不回归。
