/// explore_page_test.dart
///
/// Updated for Task 13: explore_page now consumes museumsListProvider (A1)
/// instead of the old hardcoded _museumsByCity seed.
/// Tests override museumsListProvider with fake MuseumSummary data.
import 'package:flutter/material.dart';
import 'package:gomuseum_app/l10n/app_localizations.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gomuseum_app/features/content/data/models/museum_summary_model.dart';
import 'package:gomuseum_app/features/content/presentation/providers/catalog_providers.dart';
import 'package:gomuseum_app/features/explore/presentation/pages/explore_page.dart';
import 'package:gomuseum_app/features/home/data/nearby.dart';
import 'package:gomuseum_app/features/search/data/search_api.dart';

const _fakeMuseums = [
  MuseumSummary(
    slug: 'orsay',
    name: '奥赛博物馆',
    nameEn: '奥赛博物馆',
    city: '巴黎',
    cityEn: '巴黎',
    country: 'FR',
    coordinates: [48.8599, 2.3266],
    artworkCount: 86,
  ),
  MuseumSummary(
    slug: 'louvre',
    name: '卢浮宫',
    nameEn: '卢浮宫',
    city: '巴黎',
    cityEn: '巴黎',
    country: 'FR',
    coordinates: [48.8606, 2.3376],
    artworkCount: 200,
  ),
  MuseumSummary(
    slug: 'vangogh',
    name: '梵高博物馆',
    nameEn: '梵高博物馆',
    city: '阿姆斯特丹',
    cityEn: '阿姆斯特丹',
    country: 'NL',
    coordinates: [52.3584, 4.8811],
    artworkCount: 42,
  ),
];

Widget _wrap() => ProviderScope(
      overrides: [
        museumsListProvider.overrideWith((_) async => _fakeMuseums),
        nearbyProvider
            .overrideWith((ref) async => const Nearby(NearbyMode.none, [])),
        // 搜索改走服务端 /search：输入'卢浮'返回卢浮宫命中（默认 languageProvider=en）。
        searchProvider((slug: null, q: '卢浮', lang: 'en')).overrideWith(
          (ref) => const SearchResults(museums: [
            SearchMuseumHit(slug: 'louvre', name: '卢浮宫', city: '巴黎'),
          ]),
        ),
      ],
      child: const MaterialApp(
          localizationsDelegates: AppLocalizations.localizationsDelegates,
          supportedLocales: AppLocalizations.supportedLocales,
          locale: const Locale('zh'),
          home: Scaffold(body: ExplorePage())),
    );

void main() {
  testWidgets('界面上不出现 ISO 国家码', (tester) async {
    await tester.pumpWidget(_wrap());
    await tester.pumpAndSettle();
    // fake 数据里三个馆的 country 是 FR/FR/NL。首馆大卡的页脚曾把它**原样**
    // 渲染出来,用户看到的就是一个 "FR" —— 机器码,且卡上方已有城市名。
    expect(find.text('FR'), findsNothing);
    expect(find.text('NL'), findsNothing);
  });

  testWidgets('渲染刊头、搜索框与默认城市馆列表', (tester) async {
    await tester.pumpWidget(_wrap());
    // let the FutureProvider resolve + postframe callback settle
    await tester.pumpAndSettle();
    expect(find.text('探 索'), findsOneWidget);
    expect(find.text('搜索城市、博物馆或艺术品'), findsOneWidget);
    expect(find.text('奥赛博物馆'), findsOneWidget);
    expect(find.text('卢浮宫'), findsOneWidget);
  });

  // spec 2026-09-29 §三:所有城市在同一条长列表里,点 chip 是**滚过去**,不是过滤掉别的城市
  testWidgets('点城市 chip:滚到那一段,不把别的城市过滤掉', (tester) async {
    await tester.pumpWidget(_wrap());
    await tester.pumpAndSettle();
    await tester.tap(find.text('阿姆斯特丹').first);
    await tester.pumpAndSettle();
    expect(find.text('梵高博物馆'), findsOneWidget);
    expect(find.text('奥赛博物馆', skipOffstage: false), findsOneWidget,
        reason: '巴黎的馆仍在列表里,只是滚走了');
  });

  testWidgets('输入 → 服务端搜索结果替换馆浏览', (tester) async {
    await tester.pumpWidget(_wrap());
    await tester.pumpAndSettle();
    await tester.enterText(find.byType(TextField), '卢浮');
    await tester.pump(const Duration(milliseconds: 350)); // 过 debounce
    await tester.pump(); // provider resolve
    expect(find.text('卢浮宫'), findsOneWidget); // 搜索命中
    expect(find.text('奥赛博物馆'), findsNothing); // 浏览区被搜索结果替换
  });

  testWidgets('⭐ 上下滑:滚到阿姆斯特丹那一段时,阿姆斯特丹 chip 自动高亮', (t) async {
    t.view.physicalSize = const Size(800, 560); // 矮一点:内容要真的能滚
    t.view.devicePixelRatio = 1.0;
    addTearDown(t.view.reset);
    await t.pumpWidget(_wrap());
    await t.pumpAndSettle();
    expect(_chipHighlighted(t, '巴黎'), isTrue, reason: '初始第一座城市高亮');
    expect(_chipHighlighted(t, '阿姆斯特丹'), isFalse);

    await t.drag(
        find.byType(SingleChildScrollView).last, const Offset(0, -2000));
    await t.pumpAndSettle();
    expect(_chipHighlighted(t, '阿姆斯特丹'), isTrue,
        reason: '滚到第二座城市段,chip 要跟着切过去');
    expect(_chipHighlighted(t, '巴黎'), isFalse);
  });
}

/// chip 高亮 = 背景填色(未选中是透明底)。
bool _chipHighlighted(WidgetTester t, String city) {
  final chip = find.ancestor(
      of: find.text(city).first, matching: find.byType(Container));
  final deco = (t.widget<Container>(chip.first).decoration as BoxDecoration?);
  return deco?.color != null && deco!.color != Colors.transparent;
}
