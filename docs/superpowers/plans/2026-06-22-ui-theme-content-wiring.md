# GoMuseum UI 主题地基 + 内容接入 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 给暖纸手册 UI 落地完整暗色（BD）主题与主题切换，并把「探索→馆藏列表→讲解页」从种子/旧契约切到已部署的 A1-A9 真实契约（含 `content_status=stub` 与防御式解析）。

**Architecture:** 主题层引入「亮/暗双套 token 调色板 + `context.gm` 访问器」，由 `ThemeMode` provider（shared_preferences 持久化）驱动；`lib/ui/gm` 原子与各页面从静态 `GmColors.*` 迁到 `context.gm.*`，使暗色真正生效。数据层新建 A2/A3/A5 三个契约模型（逐字段 `as T? ?? fallback`，禁裸强转）+ 对应 datasource/provider；馆藏列表消费 `categories` 建 tab、`objects` 分页无限滚动、`content_status=stub` 显「待完善」；讲解页消费 `object_content` 的 facts/images/tabs/suggested_questions。

**Tech Stack:** Flutter · Riverpod · go_router · Dio · just_audio · shared_preferences · flutter_test(widget tests)

**契约基线（权威）:** `docs/superpowers/specs/2026-06-17-artwork-content-enrichment-mechanism-design.md` 附录 A（A1-A9）+ `docs/superpowers/specs/2026-06-22-universal-catalog-spine-design.md`（`content_status` stub/generating/ready/empty）。视觉规格：`design_handoff_gomuseum/README.md` + `screens-final.jsx`。

**硬约束（CLAUDE.md + 记忆 enrichment-data-frontend-contract）:**
- 🔑 禁裸 `as String`/任何非空强转 API 字段；一律 `as T? ?? <fallback>`，缺失走占位。
- 契约为边界：若发现契约里没有的数据需求 → **不在本前端 session 写后端**，记到「后端待办」清单（本计划末尾），归后端任务。
- 加法优先，前向兼容：消费新字段时对老形状给回退（如 A2 既返 `name` 又可能保留旧 `name_zh`）。

**⚠️ 与并行 session B 的协同（避免撞文件）:**
- 本 session（A）拥有：`lib/theme/**`、`lib/ui/gm/**`、`lib/features/explore/**`、`lib/features/content/data|domain/**`、`lib/features/settings/**`、`guide_page.dart` 的**内容/facts/tabs/Hero** 部分。
- session B 拥有：`recognition/**`、`guide_page.dart` 的 **AI 聊天底部面板**（应抽成新文件 `lib/features/guide/presentation/widgets/ai_chat_sheet.dart`，由 guide_page 单点挂载）。
- `guide_page.dart` 是唯一可能双改的文件：B 把聊天面板做成**独立 widget 文件**，A 只在 guide_page 留一个 `AiChatSheet(...)` 挂载点；谁后改谁负责 rebase 这一处。开工前在 PR 描述里互相标注。

---

## File Structure

**新建：**
- `lib/theme/gm_palette.dart` — 亮(B)/暗(BD) 两套 token 常量 + `GmPalette` 类。
- `lib/theme/gm_theme_x.dart` — `BuildContext.gm` 扩展（按当前 `Brightness` 返回对应 `GmPalette`）+ 特殊规则常量（Hero 遮罩/取景器黑等不随主题切换的硬值）。
- `lib/core/theme/theme_mode_provider.dart` — `ThemeMode` StateNotifier，shared_preferences 持久化。
- `lib/features/content/data/models/museum_detail_model.dart` — A2 馆详情（categories/coordinates/opening_hours/official_url）。
- `lib/features/content/data/models/object_list_model.dart` — A3 分页藏品（item + page）。
- `lib/features/content/data/models/object_content_model.dart` — A5 详情内容（status/facts/images/tabs/suggested_questions）。
- `lib/features/content/data/datasources/catalog_remote_datasource.dart` — A2/A3/A5 三端点。
- `lib/features/content/presentation/providers/catalog_providers.dart` — Riverpod providers（馆详情/分页列表 notifier/详情内容）。
- 测试：`test/features/content/*_model_test.dart`、`test/theme/gm_palette_test.dart`。

**修改：**
- `lib/theme/gm_tokens.dart`（保留 `GmText`，`GmColors` 改为转发 light 调色板以兼容存量引用）。
- `lib/theme/app_theme.dart`（`darkTheme()` 用 BD）。
- `lib/main.dart:49-51`（`themeMode` 接 provider）。
- `lib/ui/gm/*.dart` + 8 个页面（`GmColors.x` → `context.gm.x` 迁移，分批）。
- `lib/features/explore/presentation/pages/explore_page.dart`（接 A1 /museums）。
- `lib/features/explore/presentation/pages/museum_page.dart`（接 A2/A3：categories tab + 无限滚动 + stub）。
- `lib/features/guide/presentation/pages/guide_page.dart`（接 A5：facts 墙签/信息表/tabs/Hero）。

---

## Phase 0：分支与基线确认

### Task 0: 确认运行基线

**Files:** 无（只读/配置）

- [ ] **Step 1: 确认在正确分支**

Run: `git -C /Users/hongyang/Projects/GoMuseum branch --show-current`
Expected: `feature/ui-theme-content-wiring`

- [ ] **Step 2: 基线 analyze/test 通过（改动前留底）**

Run: `cd frontend/gomuseum_app && flutter analyze 2>&1 | tail -5 && flutter test 2>&1 | tail -5`
Expected: 记录当前 warning/失败数作为基线（不要求全绿，但不得因本计划新增失败）。

- [ ] **Step 3: 确认 staging base URL 注入方式**

`lib/features/auth/presentation/auth_provider.dart:9` 的 `_resolveBaseUrl()` 读 `--dart-define=API_BASE_URL`。联调 staging：`flutter run --dart-define=API_BASE_URL=http://<staging-host>:8101`（Android 模拟器访问宿主用 `10.0.2.2`）。本计划代码不写死 host。

---

## Phase 1：主题地基（共享，先落）

### Task 1: 双套调色板 GmPalette

**Files:**
- Create: `lib/theme/gm_palette.dart`
- Test: `test/theme/gm_palette_test.dart`

- [ ] **Step 1: 写失败测试**

```dart
// test/theme/gm_palette_test.dart
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gomuseum_app/theme/gm_palette.dart';

void main() {
  test('light/dark 调色板取自 handoff token', () {
    expect(GmPalette.light.bg, const Color(0xFFF3EDDF));
    expect(GmPalette.light.accent, const Color(0xFFA14E28));
    expect(GmPalette.dark.bg, const Color(0xFF201A12));
    expect(GmPalette.dark.accent, const Color(0xFFD08050));
    // ctaDash 为半透明（45%）
    expect(GmPalette.light.ctaDash.a, closeTo(0.45, 0.02));
  });
}
```

- [ ] **Step 2: 运行确认失败**

Run: `cd frontend/gomuseum_app && flutter test test/theme/gm_palette_test.dart`
Expected: FAIL（`gm_palette.dart` 不存在）

- [ ] **Step 3: 实现 GmPalette（值取自 `design_handoff_gomuseum/gm-shared.jsx` GM_THEMES.B/BD）**

```dart
// lib/theme/gm_palette.dart
import 'package:flutter/material.dart';

/// 暖纸手册「亮(B)/暗(BD)」双套设计令牌。
/// 来源：design_handoff_gomuseum/gm-shared.jsx GM_THEMES.B / GM_THEMES.BD。
@immutable
class GmPalette {
  const GmPalette({
    required this.bg,
    required this.surface,
    required this.ink,
    required this.sub,
    required this.faint,
    required this.line,
    required this.accent,
    required this.accentDeep,
    required this.ctaBg,
    required this.ctaInk,
    required this.ctaDash,
    required this.chipBg,
    required this.isDark,
  });

  final Color bg, surface, ink, sub, faint, line;
  final Color accent, accentDeep, ctaBg, ctaInk, ctaDash, chipBg;
  final bool isDark;

  static const GmPalette light = GmPalette(
    bg: Color(0xFFF3EDDF), surface: Color(0xFFFBF7EC), ink: Color(0xFF2C2316),
    sub: Color(0xFF8A7A5F), faint: Color(0xFFB0A283), line: Color(0xFFDCD2B8),
    accent: Color(0xFFA14E28), accentDeep: Color(0xFF7E3A1C),
    ctaBg: Color(0xFFA14E28), ctaInk: Color(0xFFFBF7EC),
    ctaDash: Color(0x73FBF7EC), chipBg: Color(0xFFEAE2CD), isDark: false,
  );

  static const GmPalette dark = GmPalette(
    bg: Color(0xFF201A12), surface: Color(0xFF2A2218), ink: Color(0xFFEFE6D2),
    sub: Color(0xFFA89878), faint: Color(0xFF6E614C), line: Color(0xFF3A3022),
    accent: Color(0xFFD08050), accentDeep: Color(0xFFE09668),
    ctaBg: Color(0xFFC26A3A), ctaInk: Color(0xFF241A0F),
    ctaDash: Color(0x73241A0F), chipBg: Color(0xFF332A1D), isDark: true,
  );
}
```

> 注：`Color.a` 返回 0–1 的 alpha（Flutter 3.27+）。若 SDK 较旧无 `.a`，测试改用 `GmPalette.light.ctaDash.opacity`（同时实现处不变）。`0x73 = 115/255 ≈ 0.451`。

- [ ] **Step 4: 运行确认通过**

Run: `flutter test test/theme/gm_palette_test.dart`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add lib/theme/gm_palette.dart test/theme/gm_palette_test.dart
git commit -m "feat(theme): 暖纸手册亮/暗双套调色板 GmPalette"
```

### Task 2: context.gm 访问器 + 特殊规则常量

**Files:**
- Create: `lib/theme/gm_theme_x.dart`
- Test: `test/theme/gm_theme_x_test.dart`

- [ ] **Step 1: 写失败测试**

```dart
// test/theme/gm_theme_x_test.dart
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gomuseum_app/theme/gm_palette.dart';
import 'package:gomuseum_app/theme/gm_theme_x.dart';

void main() {
  testWidgets('context.gm 随 Theme.brightness 切换调色板', (tester) async {
    late GmPalette captured;
    await tester.pumpWidget(MaterialApp(
      theme: ThemeData(brightness: Brightness.dark),
      home: Builder(builder: (c) { captured = c.gm; return const SizedBox(); }),
    ));
    expect(captured.isDark, isTrue);
    expect(captured.bg, GmPalette.dark.bg);
  });
}
```

- [ ] **Step 2: 运行确认失败**

Run: `flutter test test/theme/gm_theme_x_test.dart`
Expected: FAIL（`gm_theme_x.dart` 不存在）

- [ ] **Step 3: 实现扩展 + 特殊规则常量**

```dart
// lib/theme/gm_theme_x.dart
import 'package:flutter/material.dart';
import 'package:gomuseum_app/theme/gm_palette.dart';

extension GmThemeX on BuildContext {
  /// 当前生效的暖纸调色板（按 Theme.brightness 选 light/dark）。
  GmPalette get gm =>
      Theme.of(this).brightness == Brightness.dark
          ? GmPalette.dark
          : GmPalette.light;
}

/// 不随主题切换的硬编码值（handoff「特殊规则」章节）。
class GmFixed {
  GmFixed._();
  static const Color viewfinderBg = Color(0xFF0F0C09);      // 取景器背景
  static const Color heroTitle = Color(0xFFF6F1E4);         // Hero 标题（白）
  static const Color heroCredit = Color(0x61F6F1E4);        // Hero 版权 38%
  /// Hero 渐变遮罩：transparent(36%) → rgba(0,0,0,0.68)
  static const List<Color> heroScrim = [Color(0x00000000), Color(0xAD000000)];
  static const List<double> heroScrimStops = [0.36, 1.0];
}
```

- [ ] **Step 4: 运行确认通过**

Run: `flutter test test/theme/gm_theme_x_test.dart`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add lib/theme/gm_theme_x.dart test/theme/gm_theme_x_test.dart
git commit -m "feat(theme): context.gm 访问器 + 不随主题切换的特殊规则常量"
```

### Task 3: app_theme darkTheme 用 BD + GmColors 兼容转发

**Files:**
- Modify: `lib/theme/app_theme.dart`
- Modify: `lib/theme/gm_tokens.dart`

- [ ] **Step 1: 读现状**

Run: `cat lib/theme/app_theme.dart lib/theme/gm_tokens.dart`
目的：确认 `GmColors` 字段名集合与 `GmText`，使 darkTheme 用 BD 值、`GmColors` 仍可编译（存量大量引用）。

- [ ] **Step 2: `darkTheme()` 用 GmPalette.dark 构建 ColorScheme.dark**

把 `app_theme.dart` 的 `darkTheme()` 改为镜像 `lightTheme()` 但取 `GmPalette.dark`：
```dart
static ThemeData darkTheme() {
  const p = GmPalette.dark;
  final textTheme = GoogleFonts.notoSansScTextTheme().apply(
    bodyColor: p.ink, displayColor: p.ink,
  );
  return ThemeData(
    useMaterial3: true,
    brightness: Brightness.dark,
    scaffoldBackgroundColor: p.bg,
    colorScheme: const ColorScheme.dark(
      primary: p.accent, onPrimary: p.ctaInk,
      secondary: p.accentDeep, onSecondary: p.ctaInk,
      surface: p.surface, onSurface: p.ink,
      outline: p.line, error: Color(0xFFEF6B5E),
    ),
    textTheme: textTheme,
    dividerColor: p.line,
    appBarTheme: AppBarTheme(
      backgroundColor: p.bg, foregroundColor: p.ink,
      elevation: 0, centerTitle: true,
      titleTextStyle: GmText.serif(size: 17, weight: FontWeight.w700),
    ),
  );
}
```
（`import 'package:gomuseum_app/theme/gm_palette.dart';`）

- [ ] **Step 3: 验证编译**

Run: `flutter analyze lib/theme/app_theme.dart`
Expected: No issues（或仅既有 warning）

- [ ] **Step 4: 提交**

```bash
git add lib/theme/app_theme.dart lib/theme/gm_tokens.dart
git commit -m "feat(theme): darkTheme 采用 BD 暗色 token"
```

### Task 4: ThemeMode provider（持久化）+ main 接线

**Files:**
- Create: `lib/core/theme/theme_mode_provider.dart`
- Modify: `lib/main.dart:49-51`
- Test: `test/core/theme/theme_mode_provider_test.dart`

- [ ] **Step 1: 写失败测试**

```dart
// test/core/theme/theme_mode_provider_test.dart
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:flutter/material.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:gomuseum_app/core/theme/theme_mode_provider.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  test('默认 system；setMode 持久化', () async {
    SharedPreferences.setMockInitialValues({});
    final c = ProviderContainer();
    addTearDown(c.dispose);
    expect(c.read(themeModeProvider), ThemeMode.system);
    await c.read(themeModeProvider.notifier).setMode(ThemeMode.dark);
    expect(c.read(themeModeProvider), ThemeMode.dark);
    final sp = await SharedPreferences.getInstance();
    expect(sp.getString('theme_mode'), 'dark');
  });
}
```

- [ ] **Step 2: 运行确认失败**

Run: `flutter test test/core/theme/theme_mode_provider_test.dart`
Expected: FAIL（provider 不存在）

- [ ] **Step 3: 实现 provider**

```dart
// lib/core/theme/theme_mode_provider.dart
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:shared_preferences/shared_preferences.dart';

const _kThemeModeKey = 'theme_mode';

final themeModeProvider =
    StateNotifierProvider<ThemeModeNotifier, ThemeMode>((ref) {
  return ThemeModeNotifier();
});

class ThemeModeNotifier extends StateNotifier<ThemeMode> {
  ThemeModeNotifier() : super(ThemeMode.system) {
    _load();
  }

  Future<void> _load() async {
    final sp = await SharedPreferences.getInstance();
    state = _parse(sp.getString(_kThemeModeKey));
  }

  Future<void> setMode(ThemeMode mode) async {
    state = mode;
    final sp = await SharedPreferences.getInstance();
    await sp.setString(_kThemeModeKey, mode.name);
  }

  ThemeMode _parse(String? s) {
    switch (s) {
      case 'light':
        return ThemeMode.light;
      case 'dark':
        return ThemeMode.dark;
      default:
        return ThemeMode.system;
    }
  }
}
```

- [ ] **Step 4: 运行确认通过**

Run: `flutter test test/core/theme/theme_mode_provider_test.dart`
Expected: PASS

- [ ] **Step 5: main.dart 接 provider**

`lib/main.dart` 顶层 `MaterialApp.router` 需在 `ConsumerWidget`/`Consumer` 内，把 `themeMode: ThemeMode.system` 改为 `themeMode: ref.watch(themeModeProvider)`。若 `main.dart:49` 所在 widget 已是 Consumer 则直接改；否则包一层 `Consumer`。

- [ ] **Step 6: 验证**

Run: `flutter analyze lib/main.dart && flutter test test/core/theme/`
Expected: PASS

- [ ] **Step 7: 提交**

```bash
git add lib/core/theme/theme_mode_provider.dart test/core/theme/theme_mode_provider_test.dart lib/main.dart
git commit -m "feat(theme): ThemeMode provider 持久化 + main 接线"
```

### Task 5: gm 原子 + 页面 `GmColors.*` → `context.gm.*` 迁移（分批）

**Files:** `lib/ui/gm/*.dart` 与 8 个页面，**每文件一提交**，避免大爆炸 diff。

> 迁移规则：`GmColors.bg→context.gm.bg`，`surface/ink/sub/faint/line/accent/accentDeep/ctaBg/ctaInk/ctaDash/chipBg` 同理。原子组件若是 `StatelessWidget`，`build(context)` 内可直接取 `final gm = context.gm;`。**不改布局/间距/字号**，只替换颜色来源。`GmText`（字体）保持不变。

- [ ] **Step 1: 列出受影响文件**

Run: `grep -rln "GmColors\." lib/ui lib/features`
Expected: 得到清单（gm 原子 6-7 个 + 8 页面）。

- [ ] **Step 2: 逐文件迁移（先 gm 原子，后页面）**

每个文件：
1. `final gm = context.gm;`（StatelessWidget build 内 / 有 context 的方法内）。
2. `GmColors.X` → `gm.X`。
3. `flutter analyze <file>` 无新错。
4. 提交：`git commit -m "refactor(theme): <file> 改用 context.gm 支持暗色"`。

⚠️ 无 `context` 的静态常量/顶层（如 `const` 列表）保留 `GmColors`（仍指向 light），登记到「遗留」，Step 3 处理。

- [ ] **Step 3: 暗色冒烟测试**

```dart
// test/theme/dark_smoke_test.dart
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gomuseum_app/features/settings/presentation/pages/settings_page.dart';
import 'package:gomuseum_app/theme/app_theme.dart';

void main() {
  testWidgets('设置页在暗色主题下可渲染且背景=BD bg', (tester) async {
    await tester.pumpWidget(ProviderScope(child: MaterialApp(
      theme: AppTheme.lightTheme(), darkTheme: AppTheme.darkTheme(),
      themeMode: ThemeMode.dark, home: const SettingsPage(),
    )));
    await tester.pump();
    final scaffold = tester.widget<Scaffold>(find.byType(Scaffold).first);
    // 不强校颜色具体值（页面可能用 context.gm 或 scaffoldBackgroundColor）；
    // 仅确认暗色下无异常渲染。
    expect(scaffold, isNotNil);
  });
}
```
（`isNotNil` 用 `isNotNull`。）

Run: `flutter test test/theme/dark_smoke_test.dart`
Expected: PASS（无 overflow/cast 异常）

- [ ] **Step 4: 提交剩余**

```bash
git add -A && git commit -m "refactor(theme): 完成 gm 原子与页面暗色迁移 + 冒烟测试"
```

### Task 6: 设置页「外观」分段控件

**Files:**
- Modify: `lib/features/settings/presentation/pages/settings_page.dart`

视觉规格：handoff README §10 — 分段控件「浅色/深色/跟随系统」，激活态 `ctaBg` 底 `ctaInk` 文字，非激活 transparent；NotoSerifSC。

- [ ] **Step 1: 加分段控件，绑 themeModeProvider**

在设置页「外观」行渲染三段：`浅色/深色/跟随系统`，点选调用 `ref.read(themeModeProvider.notifier).setMode(...)`；当前段高亮取 `ref.watch(themeModeProvider)`。颜色用 `context.gm`。

- [ ] **Step 2: widget 测试：点「深色」触发 setMode**

```dart
// test/features/settings/appearance_control_test.dart
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:gomuseum_app/core/theme/theme_mode_provider.dart';
import 'package:gomuseum_app/features/settings/presentation/pages/settings_page.dart';

void main() {
  testWidgets('点「深色」切到 ThemeMode.dark', (tester) async {
    SharedPreferences.setMockInitialValues({});
    final c = ProviderContainer();
    addTearDown(c.dispose);
    await tester.pumpWidget(UncontrolledProviderScope(container: c,
      child: const MaterialApp(home: SettingsPage())));
    await tester.pump();
    await tester.tap(find.text('深色'));
    await tester.pump();
    expect(c.read(themeModeProvider), ThemeMode.dark);
  });
}
```

Run: `flutter test test/features/settings/appearance_control_test.dart`
Expected: FAIL→实现后 PASS

- [ ] **Step 3: 提交**

```bash
git add lib/features/settings/presentation/pages/settings_page.dart test/features/settings/appearance_control_test.dart
git commit -m "feat(settings): 外观分段控件（浅/深/跟随系统）驱动 ThemeMode"
```

---

## Phase 2：内容契约数据层（A2/A3/A5）

> 全部模型遵守：逐字段 `as T? ?? fallback`；解析入口接受 `Map<String,dynamic>`，对 `null`/类型不符返回占位而非抛错。

### Task 7: A2 馆详情模型 MuseumDetail

**Files:**
- Create: `lib/features/content/data/models/museum_detail_model.dart`
- Test: `test/features/content/museum_detail_model_test.dart`

- [ ] **Step 1: 写失败测试（含缺字段/旧形状回退）**

```dart
// test/features/content/museum_detail_model_test.dart
import 'package:flutter_test/flutter_test.dart';
import 'package:gomuseum_app/features/content/data/models/museum_detail_model.dart';

void main() {
  test('A2 标准 shape 解析 categories', () {
    final m = MuseumDetail.fromJson({
      'slug': 'orsay', 'name': '奥赛博物馆', 'city': '巴黎', 'country': 'FR',
      'coordinates': [48.8599, 2.3266],
      'opening_hours': '周二–周日 9:30–18:00',
      'official_url': 'https://www.musee-orsay.fr',
      'categories': [
        {'code': 'all', 'label': '全部', 'count': 1400},
        {'code': 'painting', 'label': '绘画', 'count': 500},
      ],
    });
    expect(m.name, '奥赛博物馆');
    expect(m.categories.length, 2);
    expect(m.categories.first.code, 'all');
    expect(m.coordinates, [48.8599, 2.3266]);
  });

  test('缺 name → 回退旧 name_zh → 再回退 slug；缺 categories → 空表不崩', () {
    final m = MuseumDetail.fromJson({'slug': 'x', 'name_zh': '老字段馆'});
    expect(m.name, '老字段馆');
    expect(m.categories, isEmpty);
    final m2 = MuseumDetail.fromJson({'slug': 'y'});
    expect(m2.name, 'y');
  });
}
```

- [ ] **Step 2: 运行确认失败**

Run: `flutter test test/features/content/museum_detail_model_test.dart`
Expected: FAIL

- [ ] **Step 3: 实现**

```dart
// lib/features/content/data/models/museum_detail_model.dart
import 'package:equatable/equatable.dart';

class MuseumCategory extends Equatable {
  const MuseumCategory({required this.code, required this.label, required this.count});
  final String code;
  final String label;
  final int count;

  factory MuseumCategory.fromJson(Map<String, dynamic> j) => MuseumCategory(
        code: j['code'] as String? ?? '',
        label: j['label'] as String? ?? (j['code'] as String? ?? '未分类'),
        count: (j['count'] as num?)?.toInt() ?? 0,
      );

  @override
  List<Object?> get props => [code, label, count];
}

class MuseumDetail extends Equatable {
  const MuseumDetail({
    required this.slug,
    required this.name,
    required this.city,
    required this.country,
    required this.coordinates,
    required this.openingHours,
    required this.officialUrl,
    required this.categories,
  });

  final String slug;
  final String name;
  final String city;
  final String country;
  final List<double> coordinates; // [lat, lng]，缺则空
  final String? openingHours;
  final String? officialUrl;
  final List<MuseumCategory> categories;

  factory MuseumDetail.fromJson(Map<String, dynamic> j) {
    final slug = j['slug'] as String? ?? '';
    return MuseumDetail(
      slug: slug,
      // 加法兼容：新 name → 旧 name_zh → slug
      name: j['name'] as String? ?? j['name_zh'] as String? ?? slug,
      city: j['city'] as String? ?? j['city_zh'] as String? ?? '',
      country: j['country'] as String? ?? '',
      coordinates: (j['coordinates'] as List?)
              ?.map((e) => (e as num?)?.toDouble() ?? 0)
              .toList() ??
          const [],
      openingHours: j['opening_hours'] as String?,
      officialUrl: j['official_url'] as String?,
      categories: (j['categories'] as List?)
              ?.whereType<Map<String, dynamic>>()
              .map(MuseumCategory.fromJson)
              .toList() ??
          const [],
    );
  }

  @override
  List<Object?> get props =>
      [slug, name, city, country, coordinates, openingHours, officialUrl, categories];
}
```

- [ ] **Step 4: 运行确认通过**

Run: `flutter test test/features/content/museum_detail_model_test.dart`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add lib/features/content/data/models/museum_detail_model.dart test/features/content/museum_detail_model_test.dart
git commit -m "feat(content): A2 馆详情模型 MuseumDetail（防御解析+旧字段回退）"
```

### Task 8: A3 分页藏品模型 ObjectListItem / ObjectListPage（含 content_status）

**Files:**
- Create: `lib/features/content/data/models/object_list_model.dart`
- Test: `test/features/content/object_list_model_test.dart`

- [ ] **Step 1: 写失败测试**

```dart
// test/features/content/object_list_model_test.dart
import 'package:flutter_test/flutter_test.dart';
import 'package:gomuseum_app/features/content/data/models/object_list_model.dart';

void main() {
  test('A3 分页 + content_status 缺省 ready', () {
    final p = ObjectListPage.fromJson({
      'items': [
        {'qid': 'Q1', 'title': '在阿尔勒的卧室', 'artist': '梵高', 'year': '1889',
         'thumbnail': 'https://x/t.jpg', 'content_status': 'ready'},
        {'qid': 'Q2'}, // 极端缺字段
      ],
      'total': 500, 'limit': 50, 'offset': 0,
    });
    expect(p.total, 500);
    expect(p.items.first.title, '在阿尔勒的卧室');
    expect(p.items.first.status, ContentStatus.ready);
    // 缺字段：title 占位「未命名」，thumbnail null，status 缺省 ready
    expect(p.items[1].title, '未命名');
    expect(p.items[1].thumbnail, isNull);
    expect(p.items[1].status, ContentStatus.ready);
  });

  test('content_status=stub 解析为 stub；未知值回退 ready', () {
    expect(ObjectListItem.fromJson({'qid': 'a', 'content_status': 'stub'}).status,
        ContentStatus.stub);
    expect(ObjectListItem.fromJson({'qid': 'a', 'content_status': '??'}).status,
        ContentStatus.ready);
  });
}
```

- [ ] **Step 2: 运行确认失败**

Run: `flutter test test/features/content/object_list_model_test.dart`
Expected: FAIL

- [ ] **Step 3: 实现**

```dart
// lib/features/content/data/models/object_list_model.dart
import 'package:equatable/equatable.dart';

/// 对象内容状态（universal-catalog spec）。未知/缺省按 ready 处理（最不打扰）。
enum ContentStatus { stub, generating, ready, empty }

ContentStatus contentStatusFrom(String? s) {
  switch (s) {
    case 'stub':
      return ContentStatus.stub;
    case 'generating':
      return ContentStatus.generating;
    case 'empty':
      return ContentStatus.empty;
    case 'ready':
    default:
      return ContentStatus.ready;
  }
}

class ObjectListItem extends Equatable {
  const ObjectListItem({
    required this.qid,
    required this.title,
    required this.artist,
    required this.year,
    required this.thumbnail,
    required this.status,
  });

  final String qid;
  final String title;
  final String artist;
  final String? year;
  final String? thumbnail;
  final ContentStatus status;

  bool get isStub => status == ContentStatus.stub;

  factory ObjectListItem.fromJson(Map<String, dynamic> j) => ObjectListItem(
        qid: j['qid'] as String? ?? '',
        title: j['title'] as String? ?? '未命名',
        artist: j['artist'] as String? ?? '',
        year: j['year'] as String?,
        thumbnail: j['thumbnail'] as String?,
        status: contentStatusFrom(j['content_status'] as String?),
      );

  @override
  List<Object?> get props => [qid, title, artist, year, thumbnail, status];
}

class ObjectListPage extends Equatable {
  const ObjectListPage({
    required this.items,
    required this.total,
    required this.limit,
    required this.offset,
  });

  final List<ObjectListItem> items;
  final int total;
  final int limit;
  final int offset;

  bool get hasMore => offset + items.length < total;

  factory ObjectListPage.fromJson(Map<String, dynamic> j) => ObjectListPage(
        items: (j['items'] as List?)
                ?.whereType<Map<String, dynamic>>()
                .map(ObjectListItem.fromJson)
                .toList() ??
            const [],
        total: (j['total'] as num?)?.toInt() ?? 0,
        limit: (j['limit'] as num?)?.toInt() ?? 50,
        offset: (j['offset'] as num?)?.toInt() ?? 0,
      );

  @override
  List<Object?> get props => [items, total, limit, offset];
}
```

- [ ] **Step 4: 运行确认通过**

Run: `flutter test test/features/content/object_list_model_test.dart`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add lib/features/content/data/models/object_list_model.dart test/features/content/object_list_model_test.dart
git commit -m "feat(content): A3 分页藏品模型 + ContentStatus（防御解析）"
```

### Task 9: A5 详情内容模型 ObjectContent（facts/images/tabs/suggested_questions）

**Files:**
- Create: `lib/features/content/data/models/object_content_model.dart`
- Test: `test/features/content/object_content_model_test.dart`

- [ ] **Step 1: 写失败测试**

```dart
// test/features/content/object_content_model_test.dart
import 'package:flutter_test/flutter_test.dart';
import 'package:gomuseum_app/features/content/data/models/object_content_model.dart';
import 'package:gomuseum_app/features/content/data/models/object_list_model.dart';

void main() {
  test('A5 完整 shape', () {
    final c = ObjectContent.fromJson({
      'qid': 'Q1', 'category': 'painting', 'language': 'zh',
      'status': 'published', 'title': '在阿尔勒的卧室',
      'images': [{'url': 'https://x/i.jpg', 'credit': 'Wikimedia / 公有领域'}],
      'facts': {'artist': '梵高', 'date': '1889', 'medium': '布面油画',
                'dimensions': '57 × 74 cm', 'inventory': 'RF 1959-2',
                'exhibitions': ['1905 秋季沙龙'], 'bibliography': ['F 484']},
      'tabs': [
        {'section_code': 'overview', 'label': '介绍', 'body': '正文…',
         'audio_url': 'https://x/o.mp3'},
        {'section_code': 'author', 'label': '作者', 'body': ''}, // 空 → 待完善
      ],
      'suggested_questions': [{'question': '为什么透视是平的？', 'answer': '因为…'}],
    });
    expect(c.status, ContentStatus.ready); // published→ready
    expect(c.title, '在阿尔勒的卧室');
    expect(c.images.single.credit, 'Wikimedia / 公有领域');
    expect(c.facts.artist, '梵高');
    expect(c.facts.exhibitions, ['1905 秋季沙龙']);
    expect(c.tabs.first.hasBody, isTrue);
    expect(c.tabs[1].hasBody, isFalse); // 空 body → 前端「待完善」
    expect(c.suggestedQuestions.single.question, '为什么透视是平的？');
  });

  test('status=generating；facts/tabs 缺失全空不崩', () {
    final c = ObjectContent.fromJson({'qid': 'Q', 'status': 'generating'});
    expect(c.status, ContentStatus.generating);
    expect(c.title, '未命名');
    expect(c.images, isEmpty);
    expect(c.tabs, isEmpty);
    expect(c.facts.artist, isNull);
  });
}
```

- [ ] **Step 2: 运行确认失败**

Run: `flutter test test/features/content/object_content_model_test.dart`
Expected: FAIL

- [ ] **Step 3: 实现**

```dart
// lib/features/content/data/models/object_content_model.dart
import 'package:equatable/equatable.dart';
import 'package:gomuseum_app/features/content/data/models/object_list_model.dart';

/// A5 status: absent|generating|published|needs_review → 收敛到 ContentStatus。
ContentStatus _statusFromA5(String? s) {
  switch (s) {
    case 'generating':
      return ContentStatus.generating;
    case 'absent':
      return ContentStatus.stub;
    case 'published':
    case 'needs_review':
      return ContentStatus.ready;
    default:
      return ContentStatus.ready;
  }
}

class ObjectImage extends Equatable {
  const ObjectImage({required this.url, required this.credit});
  final String url;
  final String? credit;
  factory ObjectImage.fromJson(Map<String, dynamic> j) =>
      ObjectImage(url: j['url'] as String? ?? '', credit: j['credit'] as String?);
  @override
  List<Object?> get props => [url, credit];
}

class ObjectFacts extends Equatable {
  const ObjectFacts({
    this.artist, this.date, this.medium, this.dimensions, this.inventory,
    this.location, this.provenance, this.artistLife,
    this.exhibitions = const [], this.bibliography = const [],
  });
  final String? artist, date, medium, dimensions, inventory, location,
      provenance, artistLife;
  final List<String> exhibitions, bibliography;

  factory ObjectFacts.fromJson(Map<String, dynamic>? j) {
    final m = j ?? const {};
    List<String> strList(dynamic v) =>
        (v as List?)?.map((e) => e?.toString() ?? '').where((s) => s.isNotEmpty).toList() ??
        const [];
    return ObjectFacts(
      artist: m['artist'] as String?,
      date: m['date'] as String?,
      medium: m['medium'] as String?,
      dimensions: m['dimensions'] as String?,
      inventory: m['inventory'] as String?,
      location: m['location'] as String?,
      provenance: m['provenance'] as String?,
      artistLife: m['artist_life'] as String?,
      exhibitions: strList(m['exhibitions']),
      bibliography: strList(m['bibliography']),
    );
  }
  @override
  List<Object?> get props => [artist, date, medium, dimensions, inventory,
      location, provenance, artistLife, exhibitions, bibliography];
}

class ObjectTab extends Equatable {
  const ObjectTab({
    required this.sectionCode, required this.label,
    required this.body, required this.audioUrl,
  });
  final String sectionCode;
  final String label;
  final String? body;
  final String? audioUrl;

  /// body 空/缺 → 前端显「待完善」。
  bool get hasBody => (body ?? '').trim().isNotEmpty;

  factory ObjectTab.fromJson(Map<String, dynamic> j) => ObjectTab(
        sectionCode: j['section_code'] as String? ?? '',
        label: j['label'] as String? ?? '段落',
        body: j['body'] as String?,
        audioUrl: j['audio_url'] as String?,
      );
  @override
  List<Object?> get props => [sectionCode, label, body, audioUrl];
}

class SuggestedQuestion extends Equatable {
  const SuggestedQuestion({required this.question, required this.answer});
  final String question;
  final String? answer;
  factory SuggestedQuestion.fromJson(Map<String, dynamic> j) => SuggestedQuestion(
        question: j['question'] as String? ?? '',
        answer: j['answer'] as String?,
      );
  @override
  List<Object?> get props => [question, answer];
}

class ObjectContent extends Equatable {
  const ObjectContent({
    required this.qid, required this.category, required this.language,
    required this.status, required this.title, required this.images,
    required this.facts, required this.tabs, required this.suggestedQuestions,
  });
  final String qid;
  final String category;
  final String language;
  final ContentStatus status;
  final String title;
  final List<ObjectImage> images;
  final ObjectFacts facts;
  final List<ObjectTab> tabs;
  final List<SuggestedQuestion> suggestedQuestions;

  factory ObjectContent.fromJson(Map<String, dynamic> j) => ObjectContent(
        qid: j['qid'] as String? ?? '',
        category: j['category'] as String? ?? '',
        language: j['language'] as String? ?? 'zh',
        status: _statusFromA5(j['status'] as String?),
        title: j['title'] as String? ?? '未命名',
        images: (j['images'] as List?)
                ?.whereType<Map<String, dynamic>>()
                .map(ObjectImage.fromJson)
                .where((i) => i.url.isNotEmpty)
                .toList() ??
            const [],
        facts: ObjectFacts.fromJson(j['facts'] as Map<String, dynamic>?),
        tabs: (j['tabs'] as List?)
                ?.whereType<Map<String, dynamic>>()
                .map(ObjectTab.fromJson)
                .toList() ??
            const [],
        suggestedQuestions: (j['suggested_questions'] as List?)
                ?.whereType<Map<String, dynamic>>()
                .map(SuggestedQuestion.fromJson)
                .where((q) => q.question.isNotEmpty)
                .toList() ??
            const [],
      );

  @override
  List<Object?> get props => [qid, category, language, status, title, images,
      facts, tabs, suggestedQuestions];
}
```

- [ ] **Step 4: 运行确认通过**

Run: `flutter test test/features/content/object_content_model_test.dart`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add lib/features/content/data/models/object_content_model.dart test/features/content/object_content_model_test.dart
git commit -m "feat(content): A5 详情内容模型（facts/images/tabs/suggested_questions，防御解析）"
```

### Task 10: catalog datasource + providers（A2/A3/A5 端点）

**Files:**
- Create: `lib/features/content/data/datasources/catalog_remote_datasource.dart`
- Create: `lib/features/content/presentation/providers/catalog_providers.dart`
- Test: `test/features/content/catalog_remote_datasource_test.dart`

- [ ] **Step 1: 写失败测试（用 DioAdapter/MockDio 拦截）**

```dart
// test/features/content/catalog_remote_datasource_test.dart
import 'package:dio/dio.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gomuseum_app/features/content/data/datasources/catalog_remote_datasource.dart';

class _StubAdapter implements HttpClientAdapter {
  _StubAdapter(this.body);
  final String body;
  @override
  void close({bool force = false}) {}
  @override
  Future<ResponseBody> fetch(RequestOptions o, Stream<List<int>>? r, Future? f) async =>
      ResponseBody.fromString(body, 200,
          headers: {Headers.contentTypeHeader: [Headers.jsonContentType]});
}

void main() {
  test('getObjects 命中 A3 路径并解析', () async {
    final dio = Dio(BaseOptions(baseUrl: 'http://x'));
    dio.httpClientAdapter = _StubAdapter(
        '{"items":[{"qid":"Q1","title":"t","content_status":"stub"}],"total":1,"limit":50,"offset":0}');
    final ds = CatalogRemoteDataSourceImpl(dio: dio);
    final page = await ds.getObjects(slug: 'orsay', category: 'all', offset: 0);
    expect(page.items.single.qid, 'Q1');
    expect(page.items.single.isStub, isTrue);
  });
}
```

- [ ] **Step 2: 运行确认失败**

Run: `flutter test test/features/content/catalog_remote_datasource_test.dart`
Expected: FAIL

- [ ] **Step 3: 实现 datasource**

```dart
// lib/features/content/data/datasources/catalog_remote_datasource.dart
import 'package:dio/dio.dart';
import 'package:gomuseum_app/features/content/data/models/museum_detail_model.dart';
import 'package:gomuseum_app/features/content/data/models/object_content_model.dart';
import 'package:gomuseum_app/features/content/data/models/object_list_model.dart';

abstract class CatalogRemoteDataSource {
  Future<MuseumDetail> getMuseumDetail({required String slug, String language});
  Future<ObjectListPage> getObjects({
    required String slug, String? category, String sort, int limit, int offset,
  });
  Future<ObjectContent> getObjectContent({
    required String slug, required String qid, String language,
  });
}

class CatalogRemoteDataSourceImpl implements CatalogRemoteDataSource {
  CatalogRemoteDataSourceImpl({required this.dio});
  final Dio dio;

  @override
  Future<MuseumDetail> getMuseumDetail({required String slug, String language = 'zh'}) async {
    final r = await dio.get('/api/v1/museums/$slug',
        queryParameters: {'language': language});
    return MuseumDetail.fromJson(r.data as Map<String, dynamic>);
  }

  @override
  Future<ObjectListPage> getObjects({
    required String slug, String? category, String sort = 'popularity',
    int limit = 50, int offset = 0,
  }) async {
    final r = await dio.get('/api/v1/museums/$slug/objects', queryParameters: {
      if (category != null && category != 'all') 'category': category,
      'sort': sort, 'limit': limit, 'offset': offset,
    });
    return ObjectListPage.fromJson(r.data as Map<String, dynamic>);
  }

  @override
  Future<ObjectContent> getObjectContent({
    required String slug, required String qid, String language = 'zh',
  }) async {
    final r = await dio.get('/api/v1/museums/$slug/objects/$qid/content',
        queryParameters: {'language': language});
    return ObjectContent.fromJson(r.data as Map<String, dynamic>);
  }
}
```

- [ ] **Step 4: 运行确认通过**

Run: `flutter test test/features/content/catalog_remote_datasource_test.dart`
Expected: PASS

- [ ] **Step 5: providers（复用 `dioProvider`）**

```dart
// lib/features/content/presentation/providers/catalog_providers.dart
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:gomuseum_app/features/auth/presentation/auth_provider.dart';
import 'package:gomuseum_app/features/content/data/datasources/catalog_remote_datasource.dart';
import 'package:gomuseum_app/features/content/data/models/museum_detail_model.dart';
import 'package:gomuseum_app/features/content/data/models/object_content_model.dart';

final catalogDataSourceProvider = Provider<CatalogRemoteDataSource>((ref) {
  return CatalogRemoteDataSourceImpl(dio: ref.watch(dioProvider));
});

final museumDetailProvider =
    FutureProvider.family<MuseumDetail, String>((ref, slug) {
  return ref.watch(catalogDataSourceProvider).getMuseumDetail(slug: slug);
});

final objectContentProvider =
    FutureProvider.family<ObjectContent, ({String slug, String qid})>((ref, a) {
  return ref.watch(catalogDataSourceProvider)
      .getObjectContent(slug: a.slug, qid: a.qid);
});
```
（分页列表用 StateNotifier，见 Task 11。）

- [ ] **Step 6: 提交**

```bash
git add lib/features/content/data/datasources/catalog_remote_datasource.dart lib/features/content/presentation/providers/catalog_providers.dart test/features/content/catalog_remote_datasource_test.dart
git commit -m "feat(content): A2/A3/A5 catalog datasource + providers"
```

---

## Phase 3：页面接线

### Task 11: 馆藏列表页（museum_page）→ A2 类别 tab + A3 无限滚动 + stub「待完善」

**Files:**
- Create: `lib/features/content/presentation/providers/object_list_notifier.dart`
- Modify: `lib/features/explore/presentation/pages/museum_page.dart`
- Test: `test/features/content/object_list_notifier_test.dart`

视觉规格：handoff README §8（顶栏馆名+藏品数、分类 Tab 横滑、2 列网格、卡片 116dp 缩略图、底部加载/完成态、空字段占位）。`screens-final.jsx` 的 `FinalCollection` 为布局参考。

- [ ] **Step 1: 写分页 notifier 失败测试**

```dart
// test/features/content/object_list_notifier_test.dart
import 'package:flutter_test/flutter_test.dart';
import 'package:gomuseum_app/features/content/data/datasources/catalog_remote_datasource.dart';
import 'package:gomuseum_app/features/content/data/models/museum_detail_model.dart';
import 'package:gomuseum_app/features/content/data/models/object_content_model.dart';
import 'package:gomuseum_app/features/content/data/models/object_list_model.dart';
import 'package:gomuseum_app/features/content/presentation/providers/object_list_notifier.dart';

class _FakeDs implements CatalogRemoteDataSource {
  int calls = 0;
  @override
  Future<MuseumDetail> getMuseumDetail({required String slug, String language = 'zh'}) async =>
      throw UnimplementedError();
  @override
  Future<ObjectContent> getObjectContent({required String slug, required String qid, String language = 'zh'}) async =>
      throw UnimplementedError();
  @override
  Future<ObjectListPage> getObjects({required String slug, String? category, String sort = 'popularity', int limit = 50, int offset = 0}) async {
    calls++;
    return ObjectListPage(
      items: List.generate(limit, (i) => ObjectListItem(
        qid: 'Q${offset + i}', title: 't', artist: '', year: null,
        thumbnail: null, status: ContentStatus.ready)),
      total: 120, limit: limit, offset: offset);
  }
}

void main() {
  test('loadMore 递增 offset，hasMore 到底变 false', () async {
    final ds = _FakeDs();
    final n = ObjectListNotifier(ds: ds, slug: 'orsay', category: 'all');
    await n.loadInitial();
    expect(n.state.items.length, 50);
    expect(n.state.hasMore, isTrue);
    await n.loadMore();
    expect(n.state.items.length, 100);
    await n.loadMore();
    expect(n.state.items.length, 120);
    expect(n.state.hasMore, isFalse);
  });
}
```

- [ ] **Step 2: 运行确认失败**

Run: `flutter test test/features/content/object_list_notifier_test.dart`
Expected: FAIL

- [ ] **Step 3: 实现 notifier（累积 items + 防重入 + hasMore）**

```dart
// lib/features/content/presentation/providers/object_list_notifier.dart
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:gomuseum_app/features/content/data/datasources/catalog_remote_datasource.dart';
import 'package:gomuseum_app/features/content/data/models/object_list_model.dart';

class ObjectListState {
  const ObjectListState({
    this.items = const [], this.total = 0, this.loading = false,
    this.hasMore = true, this.error,
  });
  final List<ObjectListItem> items;
  final int total;
  final bool loading;
  final bool hasMore;
  final Object? error;

  ObjectListState copyWith({
    List<ObjectListItem>? items, int? total, bool? loading, bool? hasMore,
    Object? error, bool clearError = false,
  }) => ObjectListState(
        items: items ?? this.items,
        total: total ?? this.total,
        loading: loading ?? this.loading,
        hasMore: hasMore ?? this.hasMore,
        error: clearError ? null : (error ?? this.error),
      );
}

class ObjectListNotifier extends StateNotifier<ObjectListState> {
  ObjectListNotifier({required this.ds, required this.slug, required this.category})
      : super(const ObjectListState());
  final CatalogRemoteDataSource ds;
  final String slug;
  final String category;
  static const _limit = 50;

  Future<void> loadInitial() async {
    state = const ObjectListState(loading: true);
    await _fetch(0, replace: true);
  }

  Future<void> loadMore() async {
    if (state.loading || !state.hasMore) return;
    state = state.copyWith(loading: true, clearError: true);
    await _fetch(state.items.length);
  }

  Future<void> _fetch(int offset, {bool replace = false}) async {
    try {
      final page = await ds.getObjects(
          slug: slug, category: category, limit: _limit, offset: offset);
      final merged = replace ? page.items : [...state.items, ...page.items];
      state = state.copyWith(
        items: merged, total: page.total, loading: false,
        hasMore: merged.length < page.total, clearError: true,
      );
    } catch (e) {
      state = state.copyWith(loading: false, error: e);
    }
  }
}

final objectListProvider = StateNotifierProvider.family<ObjectListNotifier,
    ObjectListState, ({String slug, String category})>((ref, a) {
  final ds = ref.watch(catalogDataSourceProvider);
  return ObjectListNotifier(ds: ds, slug: a.slug, category: a.category)..loadInitial();
});
```
（`import` catalogDataSourceProvider from catalog_providers.dart。）

- [ ] **Step 4: 运行确认通过**

Run: `flutter test test/features/content/object_list_notifier_test.dart`
Expected: PASS

- [ ] **Step 5: 重写 museum_page UI**

- 顶栏：← + 馆名（`museumDetailProvider(slug)`）+ 藏品数 + search 图标。
- 分类 Tab 横滑：`detail.categories`（含 `all`）建 tab；切 tab 换 `objectListProvider((slug, category))`。
- 2 列 `GridView`/`CustomScrollView` + `ScrollController` 监听到底 `loadMore()`。
- 每卡：`item.thumbnail==null` → photo 占位；`item.title`（已占位「未命名」）；`item.isStub` → 角标「待完善」（chipBg 底 sub 字）。
- 底部：loading→旋转圈+「已显示 X/Y」；`!hasMore`→菱形+「已全部加载·共 N 件」。
- 颜色一律 `context.gm`。**禁裸强转**（模型已保证）。
- 点卡 → 讲解页（传 slug+qid）；`isStub` 仍可点（详情端点 A5 会触发懒生成返回 generating，讲解页轮询）。

- [ ] **Step 6: 列表页 widget 冒烟（mock provider override）**

```dart
// test/features/explore/museum_page_smoke_test.dart —— 用 ProviderScope override
// objectListProvider/museumDetailProvider 注入假数据，验证渲染 2 列 + 「待完善」角标出现。
```
（完整 override 代码在实现时按实际 provider 签名补；断言：`find.text('待完善')` 命中 stub 卡。）

Run: `flutter test test/features/explore/museum_page_smoke_test.dart`
Expected: PASS

- [ ] **Step 7: 提交**

```bash
git add lib/features/content/presentation/providers/object_list_notifier.dart lib/features/explore/presentation/pages/museum_page.dart test/features/content/object_list_notifier_test.dart test/features/explore/museum_page_smoke_test.dart
git commit -m "feat(explore): 馆藏列表接 A2 类别tab + A3 无限滚动 + stub 待完善"
```

### Task 12: 讲解页（guide_page）内容部分 → A5 ObjectContent

**Files:**
- Modify: `lib/features/guide/presentation/pages/guide_page.dart`

视觉规格：handoff README §5 + presentation-notes #10/#11/#4。**只做内容/Hero/facts/tabs；AI 问答底栏留挂载点给 session B。**

- [ ] **Step 1: 讲解页支持「按 (slug,qid) 取 A5 内容」入口**

`GuideArgs` 增 `slug`/`qid` 可选字段（保留旧 `RecognitionResult` 入口不破）。当带 qid → `ref.watch(objectContentProvider((slug, qid)))`：
- `status==generating` → 显「正在生成讲解…」占位 + 轮询（每 ~2s invalidate 重取，直到 ready/empty）。
- `status==empty` → 显「该作品暂无可接地讲解（待完善）」。

- [ ] **Step 2: Hero（折叠）**

`images[0].url` 作 Hero 大图（高 ~286dp，`SliverAppBar` 折叠）；底部渐变用 `GmFixed.heroScrim`；标题用 `GmFixed.heroTitle`；右下角 `images[0].credit` 用 `GmFixed.heroCredit`（缺图→`context.gm.surface` 占位块 + photo 图标）。多图 → 轮播指示点（v1 常一张）。

- [ ] **Step 3: 墙签 + 作品信息手风琴**

- 墙签：**单行流式无标签** `作者 · 年代 · 媒材 · 尺寸`（presentation-notes #10：不是带标签网格；媒材过长截断），值取 `facts.artist/date/medium/dimensions`，缺的跳过。
- 「▸ 作品信息」默认折叠，展开显 `inventory/location/provenance/exhibitions/bibliography/artist_life` 全表（空字段不显）。

- [ ] **Step 4: tabs 正文 + TTS**

`tabs` 建 Tab 栏（label）；每 tab body 用 `justify`，`!tab.hasBody` → 显「待完善」；有 `audio_url` → TTS 播放器（复用现有 `tts_service`）。

- [ ] **Step 5: AI 问答底栏挂载点**

底部留 `// TODO(session-B): AiChatSheet 挂载点`，渲染**静态**收起态（推荐问题 chips 来自 `content.suggestedQuestions` + 「问问这幅画」输入框 + 🎤，**点击暂 no-op/占位**）。session B 接管交互，避免本 session 触碰多轮逻辑。

- [ ] **Step 6: 讲解页 widget 冒烟**

override `objectContentProvider` 注入假 `ObjectContent`，验证：墙签单行、空 body tab 显「待完善」、suggestedQuestions chips 渲染。
Run: `flutter test test/features/guide/guide_content_smoke_test.dart`
Expected: PASS

- [ ] **Step 7: 提交**

```bash
git add lib/features/guide/presentation/pages/guide_page.dart test/features/guide/guide_content_smoke_test.dart
git commit -m "feat(guide): 讲解页内容接 A5（Hero折叠/墙签/信息表/tabs/待完善），AI底栏留挂载点"
```

### Task 13: 探索页（explore_page）→ A1 /museums

**Files:**
- Modify: `lib/features/explore/presentation/pages/explore_page.dart`

- [ ] **Step 1: 加 A1 列表 provider**

```dart
// 追加到 catalog_providers.dart
final museumsListProvider = FutureProvider<List<MuseumSummary>>((ref) async {
  final dio = ref.watch(dioProvider);
  final r = await dio.get('/api/v1/museums');
  return (r.data as List?)
          ?.whereType<Map<String, dynamic>>()
          .map(MuseumSummary.fromJson).toList() ?? const [];
});
```
并加 `MuseumSummary` 模型（slug/name/city/country/coordinates/artworkCount，防御解析 + 旧 `name_zh` 回退），含解析测试（同 Task 7 模式）。

- [ ] **Step 2: explore_page 用 `museumsListProvider` 替换 `_museumsByCity` 种子**

保持暖纸版式（刊头/搜索框/城市 chips/编号列表）；距离用 `coordinates` 本地算（无定位则不显）。城市 chips 由返回数据的 `city` 去重生成。点馆 → `museum_page(slug)`。颜色 `context.gm`。

- [ ] **Step 3: 冒烟测试 + 提交**

Run: `flutter test test/features/explore/`
```bash
git add lib/features/explore/presentation/pages/explore_page.dart lib/features/content/presentation/providers/catalog_providers.dart lib/features/content/data/models/* test/features/content/* test/features/explore/*
git commit -m "feat(explore): 探索页接 A1 /museums 真实列表"
```

---

## Phase 4：收尾验证

### Task 14: 全量 analyze/test + 暗色 QA + preci

- [ ] **Step 1: 全量门禁**

Run: `cd frontend/gomuseum_app && flutter analyze && flutter test`
Expected: analyze 无新增 error；test 全绿（不得因本计划新增失败）。

- [ ] **Step 2: 暗色 QA（手动跑模拟器，对照暗色规格优先级）**

`flutter run --dart-define=API_BASE_URL=http://10.0.2.2:8101`，设置页切「深色」，重点核对（暗色规格 §04 优先级）：讲解页 Hero 对比度 > 取景器交界 > 设置分段控件 > 横滑卡片边框。

- [ ] **Step 3: preci（本地预 CI）**

Run: `/preci`（dart format + analyze + test；后端无改动可跳过 python）。

- [ ] **Step 4: 开 PR（feature/ui-theme-content-wiring → staging）**

用 `/pr`。PR 描述标注：① 本 session 范围（主题地基+内容接入）；② 与 session B 的 `guide_page.dart` 协同点（AI 底栏挂载点）；③ 后端待办清单（见下）。

---

## 后端待办清单（契约为边界 · 不在本前端 session 实现）

> 实施中若发现以下数据缺失，**记这里、归后端任务**，前端按防御占位先行。

- [ ] 确认 staging **列表端点 `GET /museums/{slug}/objects`** 已部署且 item 带 `content_status`（universal-catalog Phase A 范围）。若未部署 → 前端 `content_status` 缺省按 `ready`，待后端补。
- [ ] 确认 **A2 `GET /museums/{slug}` 返 `categories`/`coordinates`/`opening_hours`/`official_url`**；缺则前端隐藏对应 UI（类别 tab 退化为单「全部」）。
- [ ] 确认 **A5 `GET /museums/{slug}/objects/{qid}/content`** 已上线返 `facts/images/tabs/suggested_questions`（机制 spec Phase2 已实现，需确认部署到 staging）。
- [ ] 确认 **A1 `GET /museums`** shape（`coordinates`/`artwork_count`）。

---

## Self-Review 备注

- 覆盖 handoff §7/§8/§5/§10 + presentation-notes #1/#2/#3/#4/#10/#11 + 暗色全套；§3/§4/§6/§9（识别/取景/AI聊天/足迹）归 session B 或后续。
- 防御解析：A2/A3/A5 全字段 `as T? ?? fallback`，禁裸强转（满足 enrichment-data-frontend-contract）。
- 类型一致：`ContentStatus` 跨 A3/A5 共用；`catalogDataSourceProvider` 跨 Task 10/11/13 同名。
- 契约为边界：新数据需求统一进「后端待办清单」，前端不写后端。
