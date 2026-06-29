# 讲解页改版·分层导览 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把藏品讲解页（A5 路径）从「6 模块并列信息墙」改成「分层导览」：标准导览主角 + 就地展开的预设问题 + 深度内容底部抽屉。

**Architecture:** 纯前端，前向兼容加法。新增 `default_guide` 防御解析；用纯函数 `GuideLayering` 从 `ObjectContent` 派生（主角 body/audio、抽屉 tabs、按钮数字），让页面在 `default_guide` 缺失的当前 staging 数据上也正确。新 UI 组件抽到 `lib/features/guide/presentation/widgets/`，重写 `guide_page.dart` 的 A5 body。亮/暗主题全靠 `context.gm` token。

**Tech Stack:** Flutter, Riverpod, Material 3, 现有暖纸手册组件（`GmTicketButton`/`GmIcon`/`context.gm`/`GmText`），`flutter_test`。

**设计来源（像素参考）:** `/Users/hongyang/Downloads/gm-handoff/gomuseum/project/screens-guide-v2.jsx`（只读参考，不照搬假数据）。
**Spec:** `docs/superpowers/specs/2026-06-29-guide-page-layered-redesign-design.md`。

---

## File Structure

- **Modify** `lib/features/content/data/models/object_content_model.dart` — 新增 `DefaultGuide` 值对象 + `ObjectContent.defaultGuide` 字段 + 防御解析。
- **Create** `lib/features/guide/presentation/logic/guide_layering.dart` — 纯派生逻辑（无 Flutter import，便于单测）。
- **Create** `test/features/guide/guide_layering_test.dart` — 派生逻辑单测。
- **Create** `lib/features/guide/presentation/widgets/guide_audio_bar.dart` — 预留态音频条。
- **Create** `lib/features/guide/presentation/widgets/guide_question_list.dart` — 可就地展开的预设问题列表。
- **Create** `lib/features/guide/presentation/widgets/guide_deep_sheet.dart` — 深度内容底部抽屉。
- **Modify** `lib/features/guide/presentation/pages/guide_page.dart` — 重写 `_A5Body` 为新 IA；移除主页 TabBar；接线抽屉/问题/音频条。
- **Modify** `lib/l10n/app_zh.arb`, `lib/l10n/app_en.arb`, `lib/l10n/app_fr.arb` — 新增文案 key。
- **Create** `test/features/guide/guide_redesign_widget_test.dart` — 页面 smoke + 问题展开 + 抽屉打开 widget 测试。

每条命令默认工作目录 `frontend/gomuseum_app`。

---

## Task 1: 模型新增 default_guide 防御解析

**Files:**
- Modify: `lib/features/content/data/models/object_content_model.dart`
- Test: `test/features/content/default_guide_parse_test.dart`

- [ ] **Step 1: 写失败测试**

Create `test/features/content/default_guide_parse_test.dart`:

```dart
import 'package:flutter_test/flutter_test.dart';
import 'package:gomuseum_app/features/content/data/models/object_content_model.dart';

void main() {
  test('default_guide 缺失 → null（前向兼容当前后端）', () {
    final c = ObjectContent.fromJson({
      'qid': 'Q1', 'title': 'T', 'status': 'published',
      'tabs': [], 'suggested_questions': [],
    });
    expect(c.defaultGuide, isNull);
  });

  test('default_guide 在场 → 解析 body/audio_url（audio 可空）', () {
    final c = ObjectContent.fromJson({
      'qid': 'Q1', 'title': 'T', 'status': 'published',
      'default_guide': {'body': '一分钟主线讲解', 'audio_url': null},
    });
    expect(c.defaultGuide, isNotNull);
    expect(c.defaultGuide!.body, '一分钟主线讲解');
    expect(c.defaultGuide!.audioUrl, isNull);
  });

  test('default_guide 字段类型异常 → 不抛、body 回退空串', () {
    final c = ObjectContent.fromJson({
      'qid': 'Q1', 'title': 'T', 'status': 'published',
      'default_guide': {'body': 123, 'audio_url': 456},
    });
    expect(c.defaultGuide, isNotNull);
    expect(c.defaultGuide!.body, '');
    expect(c.defaultGuide!.audioUrl, isNull);
  });
}
```

- [ ] **Step 2: 跑测试确认失败**

Run: `flutter test test/features/content/default_guide_parse_test.dart`
Expected: FAIL（`defaultGuide` getter 不存在，编译错误）。

- [ ] **Step 3: 实现 DefaultGuide + 字段**

在 `object_content_model.dart` 的 `SuggestedQuestion` 类之后、`ObjectContent` 之前插入：

```dart
class DefaultGuide extends Equatable {
  const DefaultGuide({required this.body, required this.audioUrl});
  final String body;
  final String? audioUrl;

  bool get hasBody => body.trim().isNotEmpty;

  factory DefaultGuide.fromJson(Map<String, dynamic> j) => DefaultGuide(
        // 禁裸 as String：富化字段天然可缺，统一可空 + 回退
        body: j['body'] is String ? j['body'] as String : '',
        audioUrl: j['audio_url'] is String ? j['audio_url'] as String : null,
      );

  @override
  List<Object?> get props => [body, audioUrl];
}
```

在 `ObjectContent` 的构造参数、字段、`fromJson`、`props` 四处加入 `defaultGuide`：
- 构造：`this.defaultGuide,`（放在 `required this.suggestedQuestions,` 之后，**不加 required**，默认 null）
- 字段：`final DefaultGuide? defaultGuide;`
- `fromJson` 末尾（`suggestedQuestions: ...` 之后）新增：
```dart
        defaultGuide: j['default_guide'] is Map<String, dynamic>
            ? DefaultGuide.fromJson(j['default_guide'] as Map<String, dynamic>)
            : null,
```
- `props` 列表末尾加 `defaultGuide`。

- [ ] **Step 4: 跑测试确认通过**

Run: `flutter test test/features/content/default_guide_parse_test.dart`
Expected: PASS（3 tests）。

- [ ] **Step 5: 提交**

```bash
git add lib/features/content/data/models/object_content_model.dart test/features/content/default_guide_parse_test.dart
git commit -m "feat(content): default_guide 防御解析（前向加法，null 容忍）"
```

---

## Task 2: 分层派生纯逻辑 GuideLayering

**Files:**
- Create: `lib/features/guide/presentation/logic/guide_layering.dart`
- Test: `test/features/guide/guide_layering_test.dart`

`overview` 的 `section_code` 常量 = `'overview'`（见 staging 实测）。规则见 spec「核心信息架构逻辑」。

- [ ] **Step 1: 写失败测试**

Create `test/features/guide/guide_layering_test.dart`:

```dart
import 'package:flutter_test/flutter_test.dart';
import 'package:gomuseum_app/features/content/data/models/object_content_model.dart';
import 'package:gomuseum_app/features/guide/presentation/logic/guide_layering.dart';

ObjectTab tab(String code, {String? body, String? audio}) =>
    ObjectTab(sectionCode: code, label: code, body: body, audioUrl: audio);

ObjectContent content({
  DefaultGuide? guide,
  List<ObjectTab> tabs = const [],
}) =>
    ObjectContent(
      qid: 'Q', category: '', language: 'zh',
      status: ContentStatus.ready, title: 'T',
      images: const [], facts: const ObjectFacts(),
      tabs: tabs, suggestedQuestions: const [], defaultGuide: guide,
    );

void main() {
  test('无 default_guide → overview 提升为主角，抽屉为其余 tab', () {
    final c = content(tabs: [
      tab('overview', body: '通用正文'),
      tab('artist', body: '作者'),
      tab('analysis', body: '分析'),
    ]);
    final l = GuideLayering.from(c);
    expect(l.heroBody, '通用正文');
    expect(l.heroAudioUrl, isNull);
    expect(l.deepTabs.map((t) => t.sectionCode), ['artist', 'analysis']);
    expect(l.deepCount, 2);
  });

  test('有 default_guide → 主角用它，overview 从抽屉移除（隐藏通用）', () {
    final c = content(
      guide: const DefaultGuide(body: 'DG 正文', audioUrl: 'http://a.mp3'),
      tabs: [tab('overview', body: '通用正文'), tab('artist', body: '作者')],
    );
    final l = GuideLayering.from(c);
    expect(l.heroBody, 'DG 正文');
    expect(l.heroAudioUrl, 'http://a.mp3');
    expect(l.deepTabs.map((t) => t.sectionCode), ['artist']);
  });

  test('无 overview、无 default_guide → 首个有正文 tab 当主角，其余进抽屉', () {
    final c = content(tabs: [
      tab('artist', body: '作者'),
      tab('analysis', body: '分析'),
    ]);
    final l = GuideLayering.from(c);
    expect(l.heroBody, '作者');
    expect(l.deepTabs.map((t) => t.sectionCode), ['analysis']);
  });

  test('overview body 为空 → 跳过它选首个有正文 tab 当主角', () {
    final c = content(tabs: [
      tab('overview', body: '   '),
      tab('artist', body: '作者'),
    ]);
    final l = GuideLayering.from(c);
    expect(l.heroBody, '作者');
    // 被提升的是 artist，overview 仍留抽屉
    expect(l.deepTabs.map((t) => t.sectionCode), ['overview']);
  });

  test('完全无内容 → heroBody 空、deepTabs 空、hasDeep=false', () {
    final l = GuideLayering.from(content(tabs: const []));
    expect(l.heroBody, '');
    expect(l.deepTabs, isEmpty);
    expect(l.hasDeep, isFalse);
  });
}
```

- [ ] **Step 2: 跑测试确认失败**

Run: `flutter test test/features/guide/guide_layering_test.dart`
Expected: FAIL（`guide_layering.dart` 不存在）。

- [ ] **Step 3: 实现纯逻辑**

Create `lib/features/guide/presentation/logic/guide_layering.dart`:

```dart
import 'package:gomuseum_app/features/content/data/models/object_content_model.dart';

/// 讲解页「分层导览」派生逻辑（无 Flutter 依赖，纯函数，便于单测）。
///
/// 规则（详见 spec 2026-06-29-guide-page-layered-redesign-design）：
/// - 主角 body = default_guide.body ?? 被提升 tab.body
/// - 被提升 tab：优先 section_code=='overview' 且有正文；否则首个有正文 tab
/// - 深度抽屉 = 全部 tab 去掉被提升的那个（default_guide 在场时也去掉 overview）
class GuideLayering {
  const GuideLayering({
    required this.heroBody,
    required this.heroAudioUrl,
    required this.deepTabs,
  });

  final String heroBody;
  final String? heroAudioUrl;
  final List<ObjectTab> deepTabs;

  int get deepCount => deepTabs.length;
  bool get hasDeep => deepTabs.isNotEmpty;
  bool get hasHero => heroBody.trim().isNotEmpty;

  static const String overviewCode = 'overview';

  factory GuideLayering.from(ObjectContent c) {
    final tabs = c.tabs;
    // 选被提升为主角的 tab：优先有正文的 overview，否则首个有正文 tab
    ObjectTab? promoted;
    for (final t in tabs) {
      if (t.sectionCode == overviewCode && t.hasBody) {
        promoted = t;
        break;
      }
    }
    promoted ??= tabs.where((t) => t.hasBody).cast<ObjectTab?>().firstWhere(
          (_) => true,
          orElse: () => null,
        );

    final guide = c.defaultGuide;
    final heroBody = (guide != null && guide.hasBody)
        ? guide.body
        : (promoted?.body ?? '');
    final heroAudio = (guide?.audioUrl != null && guide!.audioUrl!.isNotEmpty)
        ? guide.audioUrl
        : promoted?.audioUrl;

    // 抽屉：去掉被提升的 tab；default_guide 在场时额外去掉 overview。
    final deep = <ObjectTab>[];
    for (final t in tabs) {
      if (identical(t, promoted)) continue;
      if (guide != null && guide.hasBody && t.sectionCode == overviewCode) {
        continue;
      }
      deep.add(t);
    }

    return GuideLayering(
      heroBody: heroBody,
      heroAudioUrl: heroAudio,
      deepTabs: deep,
    );
  }
}
```

- [ ] **Step 4: 跑测试确认通过**

Run: `flutter test test/features/guide/guide_layering_test.dart`
Expected: PASS（5 tests）。

- [ ] **Step 5: 提交**

```bash
git add lib/features/guide/presentation/logic/guide_layering.dart test/features/guide/guide_layering_test.dart
git commit -m "feat(guide): 分层导览派生纯逻辑 GuideLayering + 单测"
```

---

## Task 3: l10n 新增文案

**Files:**
- Modify: `lib/l10n/app_zh.arb`, `lib/l10n/app_en.arb`, `lib/l10n/app_fr.arb`

- [ ] **Step 1: 加 key（zh）**

在 `lib/l10n/app_zh.arb` 的 `"guideInfo"` 行之后插入：

```json
  "guideStandardTour": "标准导览",
  "guideListen": "听讲解",
  "guideDiveIn": "想深入？点一下",
  "guideDeepContent": "深度内容",
  "guideAskPlaceholder": "问点什么…",
```

- [ ] **Step 2: 加 key（en）**

在 `lib/l10n/app_en.arb` 对应 `"guideInfo"` 行之后插入：

```json
  "guideStandardTour": "Standard tour",
  "guideListen": "Listen",
  "guideDiveIn": "Want more? Tap below",
  "guideDeepContent": "In depth",
  "guideAskPlaceholder": "Ask anything…",
```

- [ ] **Step 3: 加 key（fr）**

在 `lib/l10n/app_fr.arb` 对应 `"guideInfo"` 行之后插入：

```json
  "guideStandardTour": "Visite standard",
  "guideListen": "Écouter",
  "guideDiveIn": "Envie d'en savoir plus ? Touchez",
  "guideDeepContent": "En détail",
  "guideAskPlaceholder": "Posez une question…",
```

- [ ] **Step 4: 生成并验证**

Run: `flutter gen-l10n && flutter analyze lib/l10n`
Expected: 无报错；`AppLocalizations` 生成 `guideStandardTour` 等 getter。
（若 `flutter gen-l10n` 提示找不到，改用 `flutter pub get` 触发生成；本项目 `generate: true`。）

- [ ] **Step 5: 提交**

```bash
git add lib/l10n/app_zh.arb lib/l10n/app_en.arb lib/l10n/app_fr.arb
git commit -m "feat(l10n): 讲解页改版新增文案 key"
```

---

## Task 4: 预留态音频条 GuideAudioBar

**Files:**
- Create: `lib/features/guide/presentation/widgets/guide_audio_bar.dart`
- Test: `test/features/guide/guide_audio_bar_test.dart`

预留态：`audioUrl == null` 时弱化、不可点、不显示时长（TTS 未上）。`audioUrl != null` 暂时也只渲染可点外观（实际播放留给后续，不在本次范围）。

- [ ] **Step 1: 写 widget 测试**

Create `test/features/guide/guide_audio_bar_test.dart`:

```dart
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gomuseum_app/features/guide/presentation/widgets/guide_audio_bar.dart';
import 'package:gomuseum_app/l10n/app_localizations.dart';
import 'package:gomuseum_app/theme/app_theme.dart';

Widget _wrap(Widget child) => MaterialApp(
      localizationsDelegates: AppLocalizations.localizationsDelegates,
      supportedLocales: AppLocalizations.supportedLocales,
      locale: const Locale('zh'),
      theme: AppTheme.lightTheme(),
      home: Scaffold(body: child),
    );

void main() {
  testWidgets('预留态：无 audioUrl 显示"听讲解"，不显示假时长', (t) async {
    await t.pumpWidget(_wrap(const GuideAudioBar(audioUrl: null)));
    await t.pumpAndSettle();
    expect(find.text('听讲解'), findsOneWidget);
    expect(find.textContaining(':'), findsNothing); // 无 4:08 假数据
  });
}
```

> 注：`AppTheme.lightTheme()` 在 `lib/theme/app_theme.dart`（已核对）。`GmText` 来自 `gm_tokens.dart`（如该测试需要）。

- [ ] **Step 2: 跑测试确认失败**

Run: `flutter test test/features/guide/guide_audio_bar_test.dart`
Expected: FAIL（widget 不存在）。

- [ ] **Step 3: 实现**

Create `lib/features/guide/presentation/widgets/guide_audio_bar.dart`:

```dart
import 'package:flutter/material.dart';
import 'package:gomuseum_app/l10n/app_localizations.dart';
import 'package:gomuseum_app/theme/gm_theme_x.dart';
import 'package:gomuseum_app/theme/app_theme.dart';
import 'package:gomuseum_app/ui/gm/gm_icon.dart';

/// 预留态音频条（TTS 未上线前不显示时长、弱化不可点）。
class GuideAudioBar extends StatelessWidget {
  const GuideAudioBar({super.key, required this.audioUrl, this.label});

  final String? audioUrl;
  final String? label;

  @override
  Widget build(BuildContext context) {
    final gm = context.gm;
    final l10n = AppLocalizations.of(context)!;
    final reserved = audioUrl == null;
    final fg = reserved ? gm.faint : gm.sub;

    return Container(
      margin: const EdgeInsets.only(top: 11),
      padding: const EdgeInsets.fromLTRB(10, 7, 12, 7),
      decoration: BoxDecoration(
        color: gm.surface,
        border: Border.all(color: gm.line),
      ),
      child: Row(
        children: [
          Container(
            width: 27,
            height: 27,
            decoration: BoxDecoration(
              shape: BoxShape.circle,
              border: Border.all(color: gm.faint, width: 1.5),
            ),
            alignment: Alignment.center,
            child: GmIcon(GmIcons.play, size: 12, color: gm.faint, fill: true),
          ),
          const SizedBox(width: 10),
          Text(label ?? l10n.guideListen,
              style: GmText.sans(size: 12, color: fg, letterSpacing: 0.4)),
          const SizedBox(width: 12),
          Expanded(child: Container(height: 1.5, color: gm.line)),
        ],
      ),
    );
  }
}
```

> `GmIcons.play` 已存在（见 `gm_icon.dart`）。`GmText` 来自 `gm_tokens.dart`。

- [ ] **Step 4: 跑测试确认通过**

Run: `flutter test test/features/guide/guide_audio_bar_test.dart`
Expected: PASS。

- [ ] **Step 5: 提交**

```bash
git add lib/features/guide/presentation/widgets/guide_audio_bar.dart test/features/guide/guide_audio_bar_test.dart
git commit -m "feat(guide): 预留态音频条 GuideAudioBar"
```

---

## Task 5: 可展开预设问题列表 GuideQuestionList

**Files:**
- Create: `lib/features/guide/presentation/widgets/guide_question_list.dart`
- Test: `test/features/guide/guide_question_list_test.dart`

- [ ] **Step 1: 写 widget 测试**

Create `test/features/guide/guide_question_list_test.dart`:

```dart
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gomuseum_app/features/content/data/models/object_content_model.dart';
import 'package:gomuseum_app/features/guide/presentation/widgets/guide_question_list.dart';
import 'package:gomuseum_app/theme/app_theme.dart';

Widget _wrap(Widget c) =>
    MaterialApp(theme: AppTheme.lightTheme(), home: Scaffold(body: c));

void main() {
  testWidgets('点击问题就地展开答案', (t) async {
    await t.pumpWidget(_wrap(const GuideQuestionList(questions: [
      SuggestedQuestion(question: '为什么星星这么大？', answer: '因为是煤气灯。'),
    ])));
    await t.pumpAndSettle();
    expect(find.text('因为是煤气灯。'), findsNothing); // 初始收起
    await t.tap(find.text('为什么星星这么大？'));
    await t.pumpAndSettle();
    expect(find.text('因为是煤气灯。'), findsOneWidget); // 展开
  });
}
```

- [ ] **Step 2: 跑测试确认失败**

Run: `flutter test test/features/guide/guide_question_list_test.dart`
Expected: FAIL。

- [ ] **Step 3: 实现**

Create `lib/features/guide/presentation/widgets/guide_question_list.dart`:

```dart
import 'package:flutter/material.dart';
import 'package:gomuseum_app/features/content/data/models/object_content_model.dart';
import 'package:gomuseum_app/theme/gm_theme_x.dart';
import 'package:gomuseum_app/theme/app_theme.dart';

/// 预设问题竖排，点击就地展开答案（答案随契约返回，无需联网）。
class GuideQuestionList extends StatefulWidget {
  const GuideQuestionList({super.key, required this.questions});
  final List<SuggestedQuestion> questions;

  @override
  State<GuideQuestionList> createState() => _GuideQuestionListState();
}

class _GuideQuestionListState extends State<GuideQuestionList> {
  final Set<int> _open = {};

  @override
  Widget build(BuildContext context) {
    final gm = context.gm;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        for (int i = 0; i < widget.questions.length; i++)
          _row(context, gm, i, widget.questions[i]),
        Container(height: 1, color: gm.line),
      ],
    );
  }

  Widget _row(BuildContext context, gm, int i, SuggestedQuestion q) {
    final open = _open.contains(i);
    final hasAnswer = (q.answer ?? '').trim().isNotEmpty;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        GestureDetector(
          behavior: HitTestBehavior.opaque,
          onTap: hasAnswer
              ? () => setState(
                  () => open ? _open.remove(i) : _open.add(i))
              : null,
          child: Container(
            padding: const EdgeInsets.symmetric(vertical: 11),
            decoration: BoxDecoration(
              border: Border(top: BorderSide(color: gm.line)),
            ),
            child: Row(
              children: [
                Expanded(
                  child: Text(q.question,
                      style: GmText.sans(size: 13.5, height: 1.45)),
                ),
                const SizedBox(width: 10),
                SizedBox(
                  width: 14,
                  child: Text(open ? '⌄' : '›',
                      textAlign: TextAlign.center,
                      style: GmText.sans(
                          size: 18, color: gm.accent, weight: FontWeight.w700)),
                ),
              ],
            ),
          ),
        ),
        if (open && hasAnswer)
          Container(
            padding: const EdgeInsets.fromLTRB(0, 10, 0, 14),
            decoration: BoxDecoration(
              border: Border(
                  top: BorderSide(color: gm.line)), // 实现时可换虚线，见 spec
            ),
            child: Text(q.answer!,
                style: GmText.sans(size: 13, height: 1.9, color: gm.sub),
                textAlign: TextAlign.justify),
          ),
      ],
    );
  }
}
```

> 设计稿答案上边框是虚线；Flutter 无原生虚线 border，可先用实线 `gm.line`，如需虚线复用 `gm_ticket_button.dart` 里的 `_DashedBorderPainter` 思路。本步不强制虚线。

- [ ] **Step 4: 跑测试确认通过**

Run: `flutter test test/features/guide/guide_question_list_test.dart`
Expected: PASS。

- [ ] **Step 5: 提交**

```bash
git add lib/features/guide/presentation/widgets/guide_question_list.dart test/features/guide/guide_question_list_test.dart
git commit -m "feat(guide): 可展开预设问题列表 GuideQuestionList"
```

---

## Task 6: 深度内容底部抽屉 GuideDeepSheet

**Files:**
- Create: `lib/features/guide/presentation/widgets/guide_deep_sheet.dart`
- Test: `test/features/guide/guide_deep_sheet_test.dart`

照设计稿：圆角顶(18) + 柔投影 + 抓手条 + 标题 + 动态 tab + 音频条 + 正文。提供 `showGuideDeepSheet(context, tabs)` 入口（`showModalBottomSheet`, isScrollControlled）。

- [ ] **Step 1: 写 widget 测试**

Create `test/features/guide/guide_deep_sheet_test.dart`:

```dart
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gomuseum_app/features/content/data/models/object_content_model.dart';
import 'package:gomuseum_app/features/guide/presentation/widgets/guide_deep_sheet.dart';
import 'package:gomuseum_app/l10n/app_localizations.dart';
import 'package:gomuseum_app/theme/app_theme.dart';

void main() {
  testWidgets('抽屉渲染 tab 标签与首个 tab 正文，切换 tab 换正文', (t) async {
    final tabs = [
      const ObjectTab(sectionCode: 'artist', label: '作者', body: '作者正文', audioUrl: null),
      const ObjectTab(sectionCode: 'analysis', label: '分析', body: '分析正文', audioUrl: null),
    ];
    await t.pumpWidget(MaterialApp(
      localizationsDelegates: AppLocalizations.localizationsDelegates,
      supportedLocales: AppLocalizations.supportedLocales,
      locale: const Locale('zh'),
      theme: AppTheme.lightTheme(),
      home: Scaffold(body: GuideDeepSheetContent(tabs: tabs)),
    ));
    await t.pumpAndSettle();
    expect(find.text('作者'), findsOneWidget);
    expect(find.text('分析'), findsOneWidget);
    expect(find.text('作者正文'), findsOneWidget);
    await t.tap(find.text('分析'));
    await t.pumpAndSettle();
    expect(find.text('分析正文'), findsOneWidget);
  });
}
```

- [ ] **Step 2: 跑测试确认失败**

Run: `flutter test test/features/guide/guide_deep_sheet_test.dart`
Expected: FAIL。

- [ ] **Step 3: 实现**

Create `lib/features/guide/presentation/widgets/guide_deep_sheet.dart`:

```dart
import 'package:flutter/material.dart';
import 'package:gomuseum_app/features/content/data/models/object_content_model.dart';
import 'package:gomuseum_app/features/guide/presentation/widgets/guide_audio_bar.dart';
import 'package:gomuseum_app/l10n/app_localizations.dart';
import 'package:gomuseum_app/theme/gm_theme_x.dart';
import 'package:gomuseum_app/theme/app_theme.dart';
import 'package:gomuseum_app/ui/gm/gm_icon.dart';

/// 拉起「深度内容」底部抽屉。
Future<void> showGuideDeepSheet(
    BuildContext context, List<ObjectTab> tabs) {
  final gm = context.gm;
  return showModalBottomSheet<void>(
    context: context,
    isScrollControlled: true,
    backgroundColor: Colors.transparent,
    // 暗色遮罩亦由 token 决定对比；barrierColor 用半透明墨色
    barrierColor: gm.ink.withValues(alpha: 0.32),
    builder: (_) => FractionallySizedBox(
      heightFactor: 0.85,
      child: GuideDeepSheetContent(tabs: tabs),
    ),
  );
}

/// 抽屉内容（抽出便于单测，不依赖 showModalBottomSheet）。
class GuideDeepSheetContent extends StatefulWidget {
  const GuideDeepSheetContent({super.key, required this.tabs});
  final List<ObjectTab> tabs;

  @override
  State<GuideDeepSheetContent> createState() => _GuideDeepSheetContentState();
}

class _GuideDeepSheetContentState extends State<GuideDeepSheetContent> {
  int _i = 0;

  @override
  Widget build(BuildContext context) {
    final gm = context.gm;
    final l10n = AppLocalizations.of(context)!;
    final tab = widget.tabs.isEmpty ? null : widget.tabs[_i];

    return Container(
      decoration: BoxDecoration(
        color: gm.surface,
        border: Border(top: BorderSide(color: gm.line, width: 1.5)),
        borderRadius: const BorderRadius.vertical(top: Radius.circular(18)),
        boxShadow: [
          BoxShadow(
              color: gm.ink.withValues(alpha: 0.13),
              offset: const Offset(0, -8),
              blurRadius: 32),
        ],
      ),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          // 抓手条
          Padding(
            padding: const EdgeInsets.fromLTRB(0, 11, 0, 5),
            child: Center(
              child: Container(
                  width: 38,
                  height: 4,
                  decoration: BoxDecoration(
                      color: gm.faint,
                      borderRadius: BorderRadius.circular(2))),
            ),
          ),
          // 标题行
          Padding(
            padding: const EdgeInsets.fromLTRB(20, 2, 20, 10),
            child: Row(
              children: [
                Text(l10n.guideDeepContent,
                    style:
                        GmText.serif(size: 17, weight: FontWeight.w700)),
                const Spacer(),
                GestureDetector(
                  behavior: HitTestBehavior.opaque,
                  onTap: () => Navigator.of(context).maybePop(),
                  child: GmIcon(GmIcons.close, size: 19, color: gm.faint),
                ),
              ],
            ),
          ),
          Container(height: 1.5, color: gm.line),
          // Tab 栏（横滚）
          SingleChildScrollView(
            scrollDirection: Axis.horizontal,
            padding: const EdgeInsets.only(left: 12),
            child: Row(
              children: [
                for (int i = 0; i < widget.tabs.length; i++)
                  GestureDetector(
                    behavior: HitTestBehavior.opaque,
                    onTap: () => setState(() => _i = i),
                    child: Container(
                      padding: const EdgeInsets.fromLTRB(14, 9, 14, 8),
                      decoration: BoxDecoration(
                        border: Border(
                          bottom: BorderSide(
                            color: i == _i ? gm.accent : Colors.transparent,
                            width: 2.5,
                          ),
                        ),
                      ),
                      child: Text(
                        widget.tabs[i].label,
                        style: i == _i
                            ? GmText.serif(
                                size: 13.5,
                                weight: FontWeight.w700,
                                color: gm.accentDeep)
                            : GmText.sans(size: 13.5, color: gm.sub),
                      ),
                    ),
                  ),
              ],
            ),
          ),
          Container(height: 1, color: gm.line),
          // 音频条 + 正文（可滚动）
          Flexible(
            child: SingleChildScrollView(
              padding: const EdgeInsets.fromLTRB(20, 11, 20, 24),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  GuideAudioBar(audioUrl: tab?.audioUrl),
                  const SizedBox(height: 14),
                  Text(
                    (tab?.hasBody ?? false)
                        ? tab!.body!
                        : l10n.toBeRefined,
                    style: GmText.sans(
                        size: 13.5,
                        height: 1.95,
                        color: (tab?.hasBody ?? false) ? gm.ink : gm.faint),
                    textAlign: TextAlign.justify,
                  ),
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }
}
```

> `GmIcons.close` 已存在（`_A5...` 顶栏外已有 back/star；核对 `gm_icon.dart` 是否有 `close`，若无改用 `GmIcons.back` 旋转或新增 close 图标——实现时先 grep `enum GmIcons`）。

- [ ] **Step 4: 跑测试确认通过**

Run: `flutter test test/features/guide/guide_deep_sheet_test.dart`
Expected: PASS。

- [ ] **Step 5: 提交**

```bash
git add lib/features/guide/presentation/widgets/guide_deep_sheet.dart test/features/guide/guide_deep_sheet_test.dart
git commit -m "feat(guide): 深度内容底部抽屉 GuideDeepSheet（圆角顶+柔投影）"
```

---

## Task 7: 重写 A5 body 为分层导览，接线全部组件

**Files:**
- Modify: `lib/features/guide/presentation/pages/guide_page.dart`（替换 `_A5Body` 及其私有子 widget；保留状态壳/Hero/墙签/facts accordion）

把原 `_A5Body`（墙签 → facts → TabBar → TabContent → _AiChatShell）替换为新结构：
墙签 → ▸作品信息 → ◆标准导览(GuideSectionHead 风格) → GuideAudioBar(heroAudioUrl) → 主线正文 → ── 想深入？点一下 ── → GuideQuestionList → 「深度内容（N）」门票按钮(GmTicketButton) → 底部留白；底部追问栏保留为静态 BottomAskBar（沿用现有 `_AiChatShell` 的输入框壳，但去掉其中的 suggested chips，因为问题已上移）。

- [ ] **Step 1: 写页面 smoke + 集成 widget 测试**

Create `test/features/guide/guide_redesign_widget_test.dart`:

```dart
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:gomuseum_app/features/content/data/models/object_content_model.dart';
import 'package:gomuseum_app/features/guide/presentation/pages/guide_page.dart';
import 'package:gomuseum_app/features/content/presentation/providers/catalog_providers.dart';
import 'package:gomuseum_app/l10n/app_localizations.dart';
import 'package:gomuseum_app/theme/app_theme.dart';

ObjectContent _sample() => const ObjectContent(
      qid: 'Q1', category: 'painting', language: 'zh',
      status: ContentStatus.ready, title: '罗纳河上的星夜',
      images: [], facts: ObjectFacts(artist: '梵高', date: '1888'),
      tabs: [
        ObjectTab(sectionCode: 'overview', label: '通用描述', body: '主线讲解正文。', audioUrl: null),
        ObjectTab(sectionCode: 'artist', label: '作者介绍', body: '作者正文。', audioUrl: null),
      ],
      suggestedQuestions: [
        SuggestedQuestion(question: '为什么星星这么大？', answer: '因为是煤气灯。'),
      ],
    );

void main() {
  testWidgets('新版讲解页：标准导览主角 + 深度按钮 + 问题展开', (t) async {
    await t.pumpWidget(ProviderScope(
      overrides: [
        objectContentProvider((slug: 'orsay', qid: 'Q1'))
            .overrideWith((ref) => _sample()),
      ],
      child: MaterialApp(
        localizationsDelegates: AppLocalizations.localizationsDelegates,
        supportedLocales: AppLocalizations.supportedLocales,
        locale: const Locale('zh'),
        theme: AppTheme.lightTheme(),
        home: const GuidePage(args: GuideArgs(slug: 'orsay', qid: 'Q1')),
      ),
    ));
    await t.pumpAndSettle();
    expect(find.text('标准导览'), findsOneWidget);
    expect(find.text('主线讲解正文。'), findsOneWidget);
    // 深度按钮显示动态数字（去掉 overview 后 = 1）
    expect(find.textContaining('深度内容'), findsOneWidget);
    // 主页不再有并列 TabBar 的「作者介绍」标签直接可见
    expect(find.text('作者正文。'), findsNothing);
    // 问题可展开
    await t.tap(find.text('为什么星星这么大？'));
    await t.pumpAndSettle();
    expect(find.text('因为是煤气灯。'), findsOneWidget);
  });
}
```

> `objectContentProvider` 已核对：定义于 `lib/features/content/presentation/providers/catalog_providers.dart`，是 `FutureProvider.family<ObjectContent, ({String slug, String qid})>`。测试 override 用 `.overrideWith((ref) => _sample())`（返回值即可，FutureOr）。导入 `catalog_providers.dart`（不是 content_providers.dart）。

- [ ] **Step 2: 跑测试确认失败**

Run: `flutter test test/features/guide/guide_redesign_widget_test.dart`
Expected: FAIL（仍是旧 TabBar 布局，找不到「标准导览」）。

- [ ] **Step 3: 替换 _A5Body**

在 `guide_page.dart`：
1. 顶部加导入：
```dart
import 'package:gomuseum_app/features/guide/presentation/logic/guide_layering.dart';
import 'package:gomuseum_app/features/guide/presentation/widgets/guide_audio_bar.dart';
import 'package:gomuseum_app/features/guide/presentation/widgets/guide_question_list.dart';
import 'package:gomuseum_app/features/guide/presentation/widgets/guide_deep_sheet.dart';
import 'package:gomuseum_app/ui/gm/gm_ticket_button.dart';
```
2. `_buildA5Page` 中 `_syncTabController(content.tabs.length)` 及传给 `_A5Body` 的 tab/tts/speed 相关参数全部删除（主页不再有 TabBar/TTS）。`_A5Body` 改为只接 `content` 和一个 `onToggleFacts`/`factsExpanded`。`_tabController`/`_toggleTabPlay`/`_speeds` 等 A5 字段可保留（合法但不再使用）或删除——本步删除 `_syncTabController` 调用与 `_A5Body` 内 TabBar/TabContent 引用即可，不必清理所有旧字段（避免牵连 legacy 路径）。
3. 用以下新实现替换 `_A5Body` 的 `build`（保留类名 `_A5Body`，精简构造参数为 `content` + `factsExpanded` + `onToggleFacts`）：

```dart
class _A5Body extends StatelessWidget {
  const _A5Body({
    required this.content,
    required this.factsExpanded,
    required this.onToggleFacts,
  });

  final ObjectContent content;
  final bool factsExpanded;
  final VoidCallback onToggleFacts;

  @override
  Widget build(BuildContext context) {
    final gm = context.gm;
    final l10n = AppLocalizations.of(context)!;
    final layer = GuideLayering.from(content);

    return Column(
      children: [
        Expanded(
          child: SingleChildScrollView(
            padding: EdgeInsets.zero,
            child: Padding(
              padding: const EdgeInsets.symmetric(horizontal: 20),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  const SizedBox(height: 14),
                  _WallLabel(facts: content.facts),
                  const SizedBox(height: 8),
                  Container(height: 1, color: gm.line),
                  _FactsAccordion(
                    facts: content.facts,
                    expanded: factsExpanded,
                    onToggle: onToggleFacts,
                  ),
                  Container(height: 1, color: gm.line),

                  // ◆ 标准导览
                  Padding(
                    padding: const EdgeInsets.only(top: 18),
                    child: Row(children: [
                      Text('◆  ${l10n.guideStandardTour}',
                          style: GmText.serif(
                              size: 12.5,
                              weight: FontWeight.w700,
                              color: gm.accentDeep,
                              letterSpacing: 2)),
                      const SizedBox(width: 10),
                      Expanded(child: Container(height: 1, color: gm.line)),
                    ]),
                  ),
                  GuideAudioBar(audioUrl: layer.heroAudioUrl),
                  const SizedBox(height: 14),
                  if (layer.hasHero)
                    Text(layer.heroBody,
                        style: GmText.sans(size: 13.5, height: 1.95),
                        textAlign: TextAlign.justify)
                  else
                    Padding(
                      padding: const EdgeInsets.symmetric(vertical: 20),
                      child: Text(l10n.toBeRefined,
                          textAlign: TextAlign.center,
                          style: GmText.sans(size: 13, color: gm.faint)),
                    ),

                  // ── 想深入？点一下 ──
                  if (content.suggestedQuestions.isNotEmpty) ...[
                    Padding(
                      padding: const EdgeInsets.only(top: 20),
                      child: Row(children: [
                        Expanded(child: Container(height: 1, color: gm.line)),
                        Padding(
                          padding:
                              const EdgeInsets.symmetric(horizontal: 9),
                          child: Text(l10n.guideDiveIn,
                              style: GmText.sans(
                                  size: 10.5,
                                  color: gm.faint,
                                  letterSpacing: 1.2)),
                        ),
                        Expanded(child: Container(height: 1, color: gm.line)),
                      ]),
                    ),
                    const SizedBox(height: 4),
                    GuideQuestionList(questions: content.suggestedQuestions),
                  ],

                  // 📖 深度内容（N）
                  if (layer.hasDeep)
                    Padding(
                      padding: const EdgeInsets.only(top: 18),
                      child: GmTicketButton(
                        label: '${l10n.guideDeepContent}（${layer.deepCount}）',
                        icon: GmIcons.doc,
                        trailingIcon: GmIcons.arrowR,
                        onTap: () => showGuideDeepSheet(context, layer.deepTabs),
                      ),
                    ),
                  const SizedBox(height: 20),
                ],
              ),
            ),
          ),
        ),
        _AskBar(),
      ],
    );
  }
}
```

4. 新增底部追问栏静态壳 `_AskBar`（取代 `_AiChatShell`，去掉已上移的问题 chips）：

```dart
class _AskBar extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    final gm = context.gm;
    final l10n = AppLocalizations.of(context)!;
    return Container(
      padding: const EdgeInsets.fromLTRB(20, 9, 20, 14),
      decoration: BoxDecoration(
        color: gm.bg,
        border: Border(top: BorderSide(color: gm.line)),
      ),
      child: Row(children: [
        Expanded(
          child: Container(
            height: 44,
            alignment: Alignment.centerLeft,
            padding: const EdgeInsets.symmetric(horizontal: 15),
            decoration: BoxDecoration(
                color: gm.surface, border: Border.all(color: gm.line)),
            child: Text(l10n.guideAskPlaceholder,
                style: GmText.sans(size: 13, color: gm.faint)),
          ),
        ),
        const SizedBox(width: 9),
        Container(
          width: 44,
          height: 44,
          decoration:
              BoxDecoration(color: gm.ctaBg, shape: BoxShape.circle),
          alignment: Alignment.center,
          child: GmIcon(GmIcons.mic, size: 18, color: gm.ctaInk),
        ),
      ]),
    );
  }
}
```

5. 删除现已无引用的 `_TabBar` / `_TabContent` / `_TtsPlayer`(A5) / `_AiChatShell` 类与 `_A5Body` 旧参数（仅当确认 legacy 路径不引用它们；`_TtsPlayer`/`_AiChatShell` 仅 A5 用，可删）。`_buildA5Page` 里 `body:` 改为 `_A5Body(content: content, factsExpanded: _factsExpanded, onToggleFacts: () => setState(() => _factsExpanded = !_factsExpanded))`，并删去 `NestedScrollView` 之外不再需要的 TTS 字段引用。**保留** Hero SliverAppBar（设计稿 Hero 行为兼容；标题/收藏沿用）。

> `GmIcons.doc`/`GmIcons.arrowR`/`GmIcons.mic`：实现前 grep `enum GmIcons` 核对名字，缺则用最接近图标（如 book→`GmIcons.photo` 兜底或新增）。

- [ ] **Step 4: 跑测试确认通过**

Run: `flutter test test/features/guide/guide_redesign_widget_test.dart`
Expected: PASS。

- [ ] **Step 5: 全量分析 + 测试**

Run: `flutter analyze && flutter test`
Expected: analyze 0 error（warning 可有但不新增）；所有测试通过。

- [ ] **Step 6: 提交**

```bash
git add lib/features/guide/presentation/pages/guide_page.dart test/features/guide/guide_redesign_widget_test.dart
git commit -m "feat(guide): 重写讲解页 A5 为分层导览（主角+问题+深度抽屉）"
```

---

## Task 8: 暗色核对 + 真机验收清单

**Files:** 无新增；按需微调 token 用法。

- [ ] **Step 1: 暗色三处核对**

代码审查 `guide_page.dart` + 三个新 widget，确认：
- 无任何硬编码 `Color(0x...)`／`Colors.xxx`（除 Hero 渐变的固定黑、`Colors.transparent`）。`grep -n "Color(0x\|Colors\." lib/features/guide/presentation/widgets/*.dart lib/features/guide/presentation/pages/guide_page.dart`，逐条确认 Hero 渐变之外都走 `gm.*`。
- 抽屉 `barrierColor` 用 `gm.ink.withValues(alpha:0.32)`（暗色自动变深）。
- 音频条/门票按钮在 `gm.bg`(暗) 上对比足够（`gm.ctaBg` 暗色为 `#C26A3A`，ctaInk `#241A0F`，已达标）。

- [ ] **Step 2: 构建 staging APK 真机自测（亮/暗各一遍）**

```bash
flutter build apk --flavor staging --release --dart-define=API_BASE_URL=https://staging-api.gomuseum.app
```
真机打开奥赛某藏品（如 Q334138）：
- 看到「标准导览」主角正文（overview 内容）、音频条预留态（无假时长）。
- 「深度内容（5）」按钮 → 抽屉升起，5 个 tab（作者/背景/分析/意义/趣闻）可切换，圆角顶+投影。
- 2 个预设问题点击就地展开。
- 设置切深色，重看 Hero 对比/抽屉遮罩/音频条/门票按钮。

- [ ] **Step 3: 提交（如有微调）**

```bash
git add -A && git commit -m "fix(guide): 暗色 token 微调与真机核对"
```

---

## Self-Review 结论

- **Spec 覆盖：** default_guide 解析(T1)、分层派生(T2)、文案(T3)、音频预留(T4)、问题展开(T5)、深度抽屉(T6)、主页重写+去 TabBar+去"第N件"(T7)、暗色三处+真机(T8)。回退/边界由 T2 纯逻辑全覆盖并单测。
- **类型一致：** `GuideLayering.from`→`heroBody/heroAudioUrl/deepTabs/deepCount/hasDeep/hasHero`；`DefaultGuide.body/audioUrl/hasBody`；`GuideAudioBar(audioUrl,label?)`；`GuideQuestionList(questions)`；`GuideDeepSheetContent(tabs)`+`showGuideDeepSheet(context,tabs)`——跨任务一致。
- **未决依赖（实现时 grep 核对，已在步骤内标注）：** `AppTheme.lightTheme()` 工厂名、`GmIcons` 是否含 `book/close/arrowR`、`objectContentProvider` 的 family 签名与返回类型。这些是已存在代码的事实核对，非设计缺口。
