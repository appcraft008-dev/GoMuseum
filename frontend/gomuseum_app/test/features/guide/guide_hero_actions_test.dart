// 顶栏动作键（返回 / 内容反馈）的可见性。
//
// 起因：反馈键用的是整套色板里最弱的墨色（sub），而旁边的返回键用主墨色；
// 更要命的是 hero 展开时顶栏直接压在作品照片上，渐变遮罩只铺底部 160px，
// 顶部什么都没有 —— 裸着的线性图标在油画上深浅都糊，光换颜色解决不了。
//
// 所以这里钉的不是"好看"，是三条会被后人顺手改回去的东西：
// 图标用主墨色、自带一块底、读屏认得出它是什么。
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gomuseum_app/features/content/data/models/object_content_model.dart';
import 'package:gomuseum_app/features/content/data/models/object_list_model.dart';
import 'package:gomuseum_app/features/content/presentation/providers/catalog_providers.dart';
import 'package:gomuseum_app/features/guide/presentation/pages/guide_page.dart';
import 'package:gomuseum_app/features/payment/data/entitlements.dart';
import 'package:gomuseum_app/l10n/app_localizations.dart';
import 'package:gomuseum_app/theme/app_theme.dart';
import 'package:gomuseum_app/theme/gm_palette.dart';
import 'package:gomuseum_app/ui/gm/gm.dart';

// 见 guide_redesign_widget_test.dart：GuideAudioPlayer build 期无条件 watch，
// 不 override 会打真实网络并挂起。
final _entitlementsOverride =
    entitlementsProvider.overrideWith((ref) async => Entitlements.unknown);

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
            hasAudio: false),
      ],
      suggestedQuestions: [],
    );

Future<void> _pumpGuide(WidgetTester t) async {
  await t.pumpWidget(ProviderScope(
    overrides: [
      objectContentProvider((slug: 'orsay', qid: 'Q1'))
          .overrideWith((ref) => _sample()),
      _entitlementsOverride,
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
}

Finder _icon(GmIcons name) =>
    find.byWidgetPredicate((w) => w is GmIcon && w.icon == name);

void main() {
  testWidgets('反馈键用主墨色，不是那个最弱的次级色', (t) async {
    await _pumpGuide(t);
    final flag = t.widget<GmIcon>(_icon(GmIcons.flag));
    expect(flag.color, GmPalette.light.ink,
        reason: 'sub(#8A7A5F) 是次级文字色，压在作品照片上看不见');
  });

  testWidgets('两个键都自带底 —— 顶栏压在照片上时裸图标会糊掉', (t) async {
    await _pumpGuide(t);
    for (final name in [GmIcons.flag, GmIcons.back]) {
      final box = t.widget<Container>(
        find.ancestor(of: _icon(name), matching: find.byType(Container)).first,
      );
      final d = box.decoration as BoxDecoration;
      expect(d.shape, BoxShape.circle, reason: '$name 少了底衬');
      expect(d.color, GmPalette.light.surface, reason: '$name 的底是透明的');
    }
  });

  testWidgets('读屏认得出它是什么 —— 线性图标本身没有文字', (t) async {
    await _pumpGuide(t);
    final l10n = lookupAppLocalizations(const Locale('zh'));
    // 复用反馈弹层自己的标题串（已有十语），不为一个 tooltip 再开一条 key
    expect(find.bySemanticsLabel(l10n.fbTitleObject), findsOneWidget);
  });

  testWidgets('点反馈键能拉起反馈弹层', (t) async {
    await _pumpGuide(t);
    await t.tap(_icon(GmIcons.flag));
    await t.pumpAndSettle();
    final l10n = lookupAppLocalizations(const Locale('zh'));
    expect(find.text(l10n.fbTitleObject), findsWidgets);
  });
}
