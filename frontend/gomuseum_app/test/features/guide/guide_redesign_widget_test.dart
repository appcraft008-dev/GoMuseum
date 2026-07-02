import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:gomuseum_app/features/content/data/models/object_content_model.dart';
import 'package:gomuseum_app/features/content/data/models/object_list_model.dart';
import 'package:gomuseum_app/features/content/presentation/providers/catalog_providers.dart';
import 'package:gomuseum_app/features/guide/presentation/pages/guide_page.dart';
import 'package:gomuseum_app/l10n/app_localizations.dart';
import 'package:gomuseum_app/theme/app_theme.dart';

ObjectContent _sample() => const ObjectContent(
      qid: 'Q1',
      category: 'painting',
      language: 'zh',
      status: ContentStatus.ready,
      title: '罗纳河上的星夜',
      images: [],
      facts: ObjectFacts(artist: '梵高', date: '1888'),
      artist: Artist(name: '文森特·梵高', birth: '1853', death: '1890'),
      tabs: [
        ObjectTab(
            sectionCode: 'overview',
            label: '通用描述',
            body: '主线讲解正文。',
            audioUrl: null),
        ObjectTab(
            sectionCode: 'background',
            label: '创作背景',
            body: '背景正文。',
            audioUrl: null),
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

    expect(find.textContaining('标准导览'), findsOneWidget);
    expect(find.text('主线讲解正文。'), findsOneWidget);
    // 作者卡不在主页面（已移入深度抽屉首位）
    expect(find.text('文森特·梵高'), findsNothing);
    // 深度按钮（去掉 overview 后 = 1）
    expect(find.textContaining('深度内容'), findsOneWidget);
    // 主页不再并列展示深度 tab 的正文
    expect(find.text('背景正文。'), findsNothing);
    // 问题可就地展开
    await t.ensureVisible(find.text('为什么星星这么大？'));
    await t.pumpAndSettle();
    await t.tap(find.text('为什么星星这么大？'));
    await t.pumpAndSettle();
    expect(find.text('因为是煤气灯。'), findsOneWidget);

    // 打开深度抽屉 → 作者卡在内（首位）
    await t.ensureVisible(find.textContaining('深度内容'));
    await t.pumpAndSettle();
    await t.tap(find.textContaining('深度内容'));
    await t.pumpAndSettle();
    expect(find.text('文森特·梵高'), findsOneWidget);
    expect(find.text('1853 – 1890'), findsOneWidget);
  });

  testWidgets('无深度 tab 但有作者 → 深度入口仍在，抽屉含作者卡（必选常驻）', (t) async {
    const c = ObjectContent(
      qid: 'Q2',
      category: 'painting',
      language: 'zh',
      status: ContentStatus.ready,
      title: '世界的起源',
      images: [],
      facts: ObjectFacts(),
      defaultGuide: DefaultGuide(body: '主线讲解。', audioUrl: null),
      tabs: [],
      suggestedQuestions: [],
      artist: Artist(name: '库尔贝', bio: '一段经历'),
    );
    await t.pumpWidget(ProviderScope(
      overrides: [
        objectContentProvider((slug: 'orsay', qid: 'Q2'))
            .overrideWith((ref) => c),
      ],
      child: MaterialApp(
        localizationsDelegates: AppLocalizations.localizationsDelegates,
        supportedLocales: AppLocalizations.supportedLocales,
        locale: const Locale('zh'),
        theme: AppTheme.lightTheme(),
        home: const GuidePage(args: GuideArgs(slug: 'orsay', qid: 'Q2')),
      ),
    ));
    await t.pumpAndSettle();
    // 无深度 tab，入口仍露出（label = 深度内容（1），仅作者 tab）
    expect(find.textContaining('深度内容'), findsOneWidget);
    await t.ensureVisible(find.textContaining('深度内容'));
    await t.pumpAndSettle();
    await t.tap(find.textContaining('深度内容'));
    await t.pumpAndSettle();
    // 抽屉只有「作者介绍」一个 tab，默认选中 → 显示作者信息
    expect(find.text('作者介绍'), findsOneWidget);
    expect(find.text('库尔贝'), findsOneWidget);
  });
}
