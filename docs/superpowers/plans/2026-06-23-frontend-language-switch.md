# 前端讲解语言切换 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 设置页「讲解语言」从占位变为可选中/英/法，切换后讲解页、馆藏列表、详情按所选语言取后端内容。

**Architecture:** 复用既有 `languageProvider`（Locale 状态 + SharedPreferences 持久化）。设置页加语言选择弹层写 provider；内容相关 provider/datasource 读 provider 的语言码传后端，语言变 → provider 自动 invalidate 重取。纯前端，不动后端契约（后端 list/content 端点已接受 `language`）。

**Tech Stack:** Flutter + Riverpod + flutter_test。

**现状（staging 已含全部前端 UI）：**
- ✅ `languageProvider`（`features/settings/.../language_provider.dart`）：`Language extends _$Language`，`Locale build()`，`setLanguage(Locale)` 持久化。**当前无任何消费方**。
- ✅ datasource `getMuseumDetail`/`getObjectContent` 已有 `language` 参数；**`getObjects` 没有**（需加）。
- ❌ `settings_page.dart:66` 「讲解语言」`onTap: () => _comingSoon('多语言切换')`，value 写死 `'简体中文'`。
- ❌ `guide_page.dart:134` `String get _language => 'zh'` 硬编（用于 235/274/335 三处取讲解/TTS/ask）。
- ❌ `catalog_providers.dart` 的 `objectContentProvider`/`museumDetailProvider` 调 datasource **未传 language**；`object_list_notifier.dart` 的 family key `(slug, category)` 无 language。

**支持语言（前端写死，YAGNI）：** 中 `zh`、英 `en`、法 `fr`。

---

## File Structure

- **Modify** `lib/features/settings/presentation/providers/language_provider.dart` — 加 `supportedLocales` 常量 + `code`（Locale→后端语言码）+ 显示名映射。
- **Modify** `lib/features/settings/presentation/pages/settings_page.dart` — 「讲解语言」行接 languageProvider：显当前语言名 + 点击弹选择器写 provider。
- **Modify** `lib/features/content/data/datasources/catalog_remote_datasource.dart` — `getObjects` 加 `language` 参数入 query。
- **Modify** `lib/features/content/presentation/providers/catalog_providers.dart` — `objectContentProvider`/`museumDetailProvider` watch languageProvider 传 language。
- **Modify** `lib/features/content/presentation/providers/object_list_notifier.dart` — family key 加 `language`，传给 getObjects。
- **Modify** `lib/features/explore/presentation/pages/museum_page.dart` — objectListProvider 调用处补 language（watch languageProvider）。
- **Modify** `lib/features/guide/presentation/pages/guide_page.dart` — `_language` 读 languageProvider 取代硬编。

测试：
- **Create** `test/features/settings/language_code_test.dart`
- **Create** `test/features/content/get_objects_language_test.dart`

> 所有命令在 `frontend/gomuseum_app/` 下跑。每个任务后跑 `flutter analyze` 须无 error。

---

### Task 1: language_provider 加语言码与支持集

**Files:**
- Modify: `lib/features/settings/presentation/providers/language_provider.dart`
- Test: `test/features/settings/language_code_test.dart`

- [ ] **Step 1: 写失败测试**

Create `test/features/settings/language_code_test.dart`：

```dart
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gomuseum_app/features/settings/presentation/providers/language_provider.dart';

void main() {
  test('supportedLocales is zh/en/fr in order', () {
    expect(kSupportedLocales.map((l) => l.languageCode).toList(),
        ['zh', 'en', 'fr']);
  });

  test('languageDisplayName maps each supported locale', () {
    expect(languageDisplayName(const Locale('zh')), '简体中文');
    expect(languageDisplayName(const Locale('en')), 'English');
    expect(languageDisplayName(const Locale('fr')), 'Français');
  });

  test('languageDisplayName falls back to code for unknown', () {
    expect(languageDisplayName(const Locale('de')), 'de');
  });
}
```

- [ ] **Step 2: 运行确认失败**

Run: `flutter test test/features/settings/language_code_test.dart`
Expected: FAIL（`kSupportedLocales`/`languageDisplayName` 未定义）

- [ ] **Step 3: 实现**

在 `language_provider.dart` 顶部（import 之后、`@riverpod` 之前）加：

```dart
/// 讲解内容支持的语言（前端写死，与后端已生成的语言集对齐）。顺序即 UI 展示顺序。
const List<Locale> kSupportedLocales = [
  Locale('zh'),
  Locale('en'),
  Locale('fr'),
];

const Map<String, String> _kLanguageNames = {
  'zh': '简体中文',
  'en': 'English',
  'fr': 'Français',
};

/// Locale → 展示名（未知语言回退其 code）。
String languageDisplayName(Locale locale) =>
    _kLanguageNames[locale.languageCode] ?? locale.languageCode;
```

- [ ] **Step 4: 运行确认通过**

Run: `flutter test test/features/settings/language_code_test.dart`
Expected: PASS

- [ ] **Step 5: analyze + 提交**

Run: `flutter analyze lib/features/settings/presentation/providers/language_provider.dart`（无 error）

```bash
cd ../.. && git add frontend/gomuseum_app/lib/features/settings/presentation/providers/language_provider.dart frontend/gomuseum_app/test/features/settings/language_code_test.dart
git commit -m "feat(settings): languageProvider 加支持语言集与展示名"
```

---

### Task 2: getObjects 加 language 参数

**Files:**
- Modify: `lib/features/content/data/datasources/catalog_remote_datasource.dart`
- Test: `test/features/content/get_objects_language_test.dart`

参考既有：文件里 `getMuseumDetail`/`getObjectContent` 已有 `language` 参数 + `queryParameters: {'language': language}` 模式；用 `dio` 注入。测试参考既有 `test/features/content/catalog_remote_datasource_test.dart`（用 dio mock/adapter）。

- [ ] **Step 1: 先看既有 datasource 测试怎么 mock dio**

Run: `cat test/features/content/catalog_remote_datasource_test.dart`
据其 mock 方式（DioAdapter / MockDio）写本任务测试，保持一致。

- [ ] **Step 2: 写失败测试**

Create `test/features/content/get_objects_language_test.dart`，断言 `getObjects(..., language: 'en')` 把 `language=en` 放进请求 query。**按上一步看到的既有 mock 风格实现**（若用 `http_mock_adapter` 的 DioAdapter，断言 query 含 language；若用别的，照搬其断言方式）。最小骨架：

```dart
import 'package:dio/dio.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gomuseum_app/features/content/data/datasources/catalog_remote_datasource.dart';
// + 既有测试用的 mock 包 import

void main() {
  test('getObjects sends language query param', () async {
    // 用与 catalog_remote_datasource_test.dart 相同的 mock 机制：
    // 拦截 GET /api/v1/museums/orsay/objects，捕获 queryParameters，
    // 返回 {"items":[],"total":0,"limit":50,"offset":0}
    // 调 ds.getObjects(slug:'orsay', language:'en')
    // 断言捕获的 query['language'] == 'en'
  });
}
```

> 实现者：请按既有 `catalog_remote_datasource_test.dart` 的具体 mock API 把上面骨架写成可跑的断言（捕获 query 并断言 `language == 'en'`）。

- [ ] **Step 3: 运行确认失败**

Run: `flutter test test/features/content/get_objects_language_test.dart`
Expected: FAIL（`getObjects` 不接受 `language` 命名参数 → 编译错）

- [ ] **Step 4: 实现**

在 `catalog_remote_datasource.dart`：

抽象方法签名加 language：
```dart
  Future<ObjectListPage> getObjects({
    required String slug,
    String? category,
    String sort,
    int limit,
    int offset,
    String language,
  });
```

实现改为：
```dart
  @override
  Future<ObjectListPage> getObjects({
    required String slug,
    String? category,
    String sort = 'popularity',
    int limit = 50,
    int offset = 0,
    String language = 'zh',
  }) async {
    final r = await dio.get('/api/v1/museums/$slug/objects', queryParameters: {
      if (category != null && category != 'all') 'category': category,
      'sort': sort,
      'limit': limit,
      'offset': offset,
      'language': language,
    });
    return ObjectListPage.fromJson(r.data as Map<String, dynamic>);
  }
```

- [ ] **Step 5: 运行确认通过**

Run: `flutter test test/features/content/get_objects_language_test.dart test/features/content/catalog_remote_datasource_test.dart`
Expected: PASS（含既有 datasource 测试不回归）

- [ ] **Step 6: analyze + 提交**

Run: `flutter analyze lib/features/content/data/datasources/catalog_remote_datasource.dart`（无 error）

```bash
cd ../.. && git add frontend/gomuseum_app/lib/features/content/data/datasources/catalog_remote_datasource.dart frontend/gomuseum_app/test/features/content/get_objects_language_test.dart
git commit -m "feat(catalog): getObjects 加 language 参数"
```

---

### Task 3: 内容 provider 接 languageProvider

**Files:**
- Modify: `lib/features/content/presentation/providers/catalog_providers.dart`
- Modify: `lib/features/content/presentation/providers/object_list_notifier.dart`
- Modify: `lib/features/explore/presentation/pages/museum_page.dart`

本任务让内容读取按当前语言走、语言变自动重取。**无新单测**（属集成接线，靠 analyze + 既有测试 + 手验）；但必须保证既有测试不回归。

- [ ] **Step 1: 看清现有调用点**

Run（在 `frontend/gomuseum_app/`）：
```
sed -n '1,40p' lib/features/content/presentation/providers/catalog_providers.dart
sed -n '39,90p' lib/features/content/presentation/providers/object_list_notifier.dart
grep -n "objectListProvider\|languageProvider\|_selectedCategory" lib/features/explore/presentation/pages/museum_page.dart
```

- [ ] **Step 2: catalog_providers.dart — content/detail 传 language**

`catalog_providers.dart` 顶部加 import：
```dart
import 'package:gomuseum_app/features/settings/presentation/providers/language_provider.dart';
```

`objectContentProvider` 改为读语言并传入（语言变 → 自动重取）：
```dart
final objectContentProvider =
    FutureProvider.family<ObjectContent, ({String slug, String qid})>((ref, a) {
  final lang = ref.watch(languageProvider).languageCode;
  return ref
      .watch(catalogDataSourceProvider)
      .getObjectContent(slug: a.slug, qid: a.qid, language: lang);
});
```

`museumDetailProvider` 同样：
```dart
final museumDetailProvider =
    FutureProvider.family<MuseumDetail, String>((ref, slug) {
  final lang = ref.watch(languageProvider).languageCode;
  return ref
      .watch(catalogDataSourceProvider)
      .getMuseumDetail(slug: slug, language: lang);
});
```

- [ ] **Step 3: object_list_notifier.dart — family key 加 language**

把 family record 类型从 `({String slug, String category})` 改为含 language，notifier 持有并传给 getObjects。改 `objectListProvider`：

```dart
final objectListProvider = StateNotifierProvider.family<ObjectListNotifier,
    ObjectListState, ({String slug, String category, String language})>(
    (ref, a) {
  final ds = ref.watch(catalogDataSourceProvider);
  return ObjectListNotifier(
      ds: ds, slug: a.slug, category: a.category, language: a.language)
    ..loadInitial();
});
```

`ObjectListNotifier` 加 `final String language;` 字段（构造函数补 `required this.language`），`_fetch` 里 getObjects 调用补 `language: language`：

```dart
      final page = await ds.getObjects(
          slug: slug,
          category: category,
          limit: _limit,
          offset: offset,
          language: language);
```

- [ ] **Step 4: museum_page.dart — 调用处补 language**

在 `museum_page.dart` 用到 `objectListProvider((slug:..., category:...))` 的每一处，补 `language`。先在 build 里取语言：
```dart
    final lang = ref.watch(languageProvider).languageCode;
```
并加 import：
```dart
import 'package:gomuseum_app/features/settings/presentation/providers/language_provider.dart';
```
把每个 `objectListProvider((slug: ..., category: ...))` 改为 `objectListProvider((slug: ..., category: ..., language: lang))`（Step 1 grep 出的全部点，含 read/watch/invalidate）。

> ⚠️ 该文件有多处（约 50/53/287/311 行）引用该 family key——**全部**改成带 language 的三元 record，否则类型不匹配编译失败。

- [ ] **Step 5: analyze 全绿 + 既有测试不回归**

Run:
```
flutter analyze lib/features/content/presentation/providers/catalog_providers.dart lib/features/content/presentation/providers/object_list_notifier.dart lib/features/explore/presentation/pages/museum_page.dart
flutter test test/features/content/ test/features/explore/
```
Expected: analyze 无 error；测试 PASS（既有列表/详情测试若用了 objectListProvider 的旧 key，需同步改 key——一并修，记录在提交里）。

- [ ] **Step 6: 提交**

```bash
cd ../.. && git add frontend/gomuseum_app/lib/features/content/presentation/providers/catalog_providers.dart frontend/gomuseum_app/lib/features/content/presentation/providers/object_list_notifier.dart frontend/gomuseum_app/lib/features/explore/presentation/pages/museum_page.dart frontend/gomuseum_app/test/
git commit -m "feat(catalog): 内容/列表/详情 provider 按 languageProvider 取数"
```

---

### Task 4: guide_page 读 languageProvider

**Files:**
- Modify: `lib/features/guide/presentation/pages/guide_page.dart`

- [ ] **Step 1: 看 _language 定义与用处**

Run: `grep -n "_language\|languageProvider\|import.*language_provider" lib/features/guide/presentation/pages/guide_page.dart`
（235/274/335 三处用 `_language`；134 行 `String get _language => 'zh';`）

- [ ] **Step 2: 改 _language 读 provider**

顶部加 import：
```dart
import 'package:gomuseum_app/features/settings/presentation/providers/language_provider.dart';
```

把 `String get _language => 'zh';` 改为读 provider（guide_page 是 ConsumerStatefulWidget，`ref` 可用）：
```dart
  String get _language => ref.read(languageProvider).languageCode;
```

> 注：`objectContentProvider` 已在 Task 3 改为 watch languageProvider，故讲解 tab 内容会随语言自动重取；`_language` 这里供 TTS/ask（235/274/335）取当前语言用 `ref.read` 即可（动作触发时读当前值）。

- [ ] **Step 3: analyze + 提交**

Run: `flutter analyze lib/features/guide/presentation/pages/guide_page.dart`（无 error）

```bash
cd ../.. && git add frontend/gomuseum_app/lib/features/guide/presentation/pages/guide_page.dart
git commit -m "feat(guide): 讲解语言读 languageProvider 取代硬编 zh"
```

---

### Task 5: 设置页语言选择器

**Files:**
- Modify: `lib/features/settings/presentation/pages/settings_page.dart`

参考既有：`_row(gm:, icon:, label:, value:, onTap:)`（247 行）；`_comingSoon`（357 行，弹 SnackBar）；文件已 import flutter_riverpod、gm 主题。设置页是 ConsumerStatefulWidget，`ref` 可用。`languageProvider`/`kSupportedLocales`/`languageDisplayName` 来自 Task 1。

- [ ] **Step 1: 顶部加 import**

```dart
import 'package:gomuseum_app/features/settings/presentation/providers/language_provider.dart';
```

- [ ] **Step 2: 「讲解语言」行接 provider**

把 66 行附近的「讲解语言」`_row` 改为：value 显当前语言名、onTap 弹选择器。在 `build` 里（`final gm = context.gm;` 附近）取：
```dart
    final currentLocale = ref.watch(languageProvider);
```
并把该 `_row` 改为：
```dart
            _row(
              gm: gm,
              icon: GmIcons.globe,
              label: '讲解语言',
              value: languageDisplayName(currentLocale),
              onTap: _pickLanguage,
            ),
```

- [ ] **Step 3: 加 _pickLanguage 方法**

在 `_comingSoon`（357 行）附近加：
```dart
  Future<void> _pickLanguage() async {
    final gm = context.gm;
    final current = ref.read(languageProvider);
    final picked = await showModalBottomSheet<Locale>(
      context: context,
      backgroundColor: gm.bg,
      builder: (ctx) => SafeArea(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            const SizedBox(height: 8),
            for (final loc in kSupportedLocales)
              ListTile(
                title: Text(languageDisplayName(loc),
                    style: GmText.sans(size: 15, color: gm.ink)),
                trailing: loc.languageCode == current.languageCode
                    ? GmIcon(GmIcons.check, size: 18, color: gm.ink)
                    : null,
                onTap: () => Navigator.of(ctx).pop(loc),
              ),
            const SizedBox(height: 8),
          ],
        ),
      ),
    );
    if (picked != null) {
      await ref.read(languageProvider.notifier).setLanguage(picked);
    }
  }
```

> ⚠️ 校验：`GmIcons.check` 是否存在——若不存在，用一个已有的对勾类图标（grep `GmIcons.` 看可用项，如 `GmIcons.chevR` 不合适则换文本「·当前」或省略 trailing）。实现者按实际 GmIcons 调整。

- [ ] **Step 4: analyze 全绿**

Run: `flutter analyze lib/features/settings/presentation/pages/settings_page.dart`
Expected: 无 error（若 `GmIcons.check` 不存在会报，按上注调整）。

- [ ] **Step 5: 既有 settings 测试不回归 + 提交**

Run: `flutter test test/features/settings/`
Expected: PASS

```bash
cd ../.. && git add frontend/gomuseum_app/lib/features/settings/presentation/pages/settings_page.dart
git commit -m "feat(settings): 讲解语言选择器(中/英/法)写 languageProvider"
```

---

### Task 6: 全量 analyze + 测试

**Files:** 无（验证任务）

- [ ] **Step 1: 全量 analyze**

Run（在 `frontend/gomuseum_app/`）：`flutter analyze`
Expected: 无 error（warning 若是既有存量可接受，但本次改动文件不得引入新 error/warning）。

- [ ] **Step 2: 全量测试**

Run: `flutter test`
Expected: 全 PASS（25+ 既有 + 新增）。若有因 provider key 改动而挂的既有测试，修到绿。

- [ ] **Step 3: 提交（若 Step 2 有修复）**

```bash
cd ../.. && git add frontend/gomuseum_app/
git commit -m "test(catalog): 修复语言切换引入的 provider key 测试"
```
（无修复则跳过。）

---

## Self-Review

- **链路完整**：设置页选语言（Task 5）→ 写 languageProvider（Task 1 基建）→ 内容/列表/详情 provider watch 它自动重取（Task 2/3）→ 讲解页 TTS/ask 读它（Task 4）。
- **语言变驱动刷新**：objectContentProvider/museumDetailProvider `watch` languageProvider（变即 invalidate）；objectListProvider family key 含 language（变即新实例 loadInitial）。
- **后端已就绪**：list/content/detail 端点均接受 `language`（content 端点 PR 已上；list 端点本批 PR #77 已上 staging）。纯前端改，无后端契约改动。
- **类型一致**：getObjects 命名参数 `language`（Task 2 定义、Task 3 调用）；objectListProvider family key 三元 record（Task 3 全调用点同步）。
- **YAGNI**：仅中/英/法写死；不做"按馆动态语言集"（将来后端给 supported_languages 再说）。
- **回退**：languageDisplayName 未知→code；datasource language 默认 'zh'。

## 验证（手动）

合前在本地或合 staging 后：
1. 设置页「讲解语言」显示当前语言；点开弹中/英/法，选「English」。
2. 进奥赛馆藏列表 → 标题变英文（需后端已生成 en，奥赛已有）。
3. 进某讲解页 → tab 内容为英文。
4. 切回「简体中文」→ 列表/讲解回中文。
5. 杀进程重进 → 语言保持（SharedPreferences 持久化）。
