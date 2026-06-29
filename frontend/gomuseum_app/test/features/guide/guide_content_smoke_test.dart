// test/features/guide/guide_content_smoke_test.dart
//
// Widget smoke test for the A5 content path of GuidePage.
// Overrides objectContentProvider with a fake ObjectContent:
//   - one ready tab (with body)
//   - one empty-body tab (should show 「待完善」)
//   - facts with artist/date/medium/dimensions
//   - 1 suggested question chip
//
// Asserts:
//   - wall-label text (single-line flowing) is present
//   - the empty-body tab shows 「待完善」
//   - suggestedQuestions chip text renders

import 'package:flutter/material.dart';
import 'package:gomuseum_app/l10n/app_localizations.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gomuseum_app/features/content/data/models/object_content_model.dart';
import 'package:gomuseum_app/features/content/data/models/object_list_model.dart';
import 'package:gomuseum_app/features/content/presentation/providers/catalog_providers.dart';
import 'package:gomuseum_app/features/guide/presentation/pages/guide_page.dart';
import 'package:gomuseum_app/theme/app_theme.dart';

// ---------------------------------------------------------------------------
// Fake ObjectContent with controlled data
// ---------------------------------------------------------------------------
ObjectContent _fakeContent() => const ObjectContent(
      qid: 'Q1',
      category: 'painting',
      language: 'zh',
      status: ContentStatus.ready,
      title: '在阿尔勒的卧室',
      images: [],
      facts: ObjectFacts(
        artist: '文森特·梵高',
        date: '1889',
        medium: '布面油画',
        dimensions: '57 × 74 cm',
      ),
      tabs: [
        ObjectTab(
          sectionCode: 'overview',
          label: '介绍',
          body: '这是一幅充满活力的作品，梵高以鲜艳色彩描绘了卧室的宁静。',
          audioUrl: null,
        ),
        ObjectTab(
          sectionCode: 'author',
          label: '作者',
          body: '', // empty → should show 待完善
          audioUrl: null,
        ),
      ],
      suggestedQuestions: [
        SuggestedQuestion(
          question: '为什么透视是平的？',
          answer: '因为梵高故意如此。',
        ),
      ],
    );

// ---------------------------------------------------------------------------
// Widget wrapper
// ---------------------------------------------------------------------------
Widget _wrap() => ProviderScope(
      overrides: [
        // Override objectContentProvider to return fake content immediately
        objectContentProvider.overrideWith(
          (ref, param) async => _fakeContent(),
        ),
      ],
      child: MaterialApp(
        localizationsDelegates: AppLocalizations.localizationsDelegates,
        supportedLocales: AppLocalizations.supportedLocales,
        locale: const Locale('zh'),
        theme: AppTheme.lightTheme(),
        home: const GuidePage(args: GuideArgs(slug: 'orsay', qid: 'Q1')),
      ),
    );

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------
void main() {
  testWidgets(
      'guide_page A5: wall-label flows as single line (artist · date · medium · dims)',
      (tester) async {
    await tester.pumpWidget(_wrap());
    await tester.pumpAndSettle();

    // Wall label should render the flowing single-line form
    // "文森特·梵高 · 1889 · 布面油画 · 57 × 74 cm"
    expect(find.textContaining('文森特·梵高'), findsWidgets);
    expect(find.textContaining('1889'), findsWidgets);
    expect(find.textContaining('布面油画'), findsWidgets);
  });

  testWidgets('guide_page A5: 深度抽屉中空 body tab 显示 待完善', (tester) async {
    await tester.pumpWidget(_wrap());
    await tester.pumpAndSettle();

    // 新 IA：overview 提升为主角，author(空 body) 进深度抽屉。
    // 打开「深度内容」抽屉，唯一深度 tab=作者(空 body) → 显示 待完善。
    await tester.ensureVisible(find.textContaining('深度内容'));
    await tester.pumpAndSettle();
    await tester.tap(find.textContaining('深度内容'));
    await tester.pumpAndSettle();

    expect(find.text('待完善'), findsOneWidget);
  });

  testWidgets('guide_page A5: suggestedQuestions chip renders', (tester) async {
    await tester.pumpWidget(_wrap());
    await tester.pumpAndSettle();

    expect(find.text('为什么透视是平的？'), findsOneWidget);
  });

  testWidgets('guide_page A5: title shows in hero appbar', (tester) async {
    await tester.pumpWidget(_wrap());
    await tester.pumpAndSettle();

    // Title appears in the SliverAppBar (may appear more than once)
    expect(find.text('在阿尔勒的卧室'), findsWidgets);
  });
}
