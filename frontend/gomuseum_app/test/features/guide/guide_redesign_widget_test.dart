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
      tabs: [
        ObjectTab(
            sectionCode: 'overview',
            label: '通用描述',
            body: '主线讲解正文。',
            audioUrl: null),
        ObjectTab(
            sectionCode: 'artist',
            label: '作者介绍',
            body: '作者正文。',
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
    // 深度按钮（去掉 overview 后 = 1）
    expect(find.textContaining('深度内容'), findsOneWidget);
    // 主页不再并列展示深度 tab 的正文
    expect(find.text('作者正文。'), findsNothing);
    // 问题可就地展开
    await t.ensureVisible(find.text('为什么星星这么大？'));
    await t.pumpAndSettle();
    await t.tap(find.text('为什么星星这么大？'));
    await t.pumpAndSettle();
    expect(find.text('因为是煤气灯。'), findsOneWidget);
  });
}
