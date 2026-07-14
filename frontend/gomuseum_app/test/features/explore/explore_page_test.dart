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
  testWidgets('渲染刊头、搜索框与默认城市馆列表', (tester) async {
    await tester.pumpWidget(_wrap());
    // let the FutureProvider resolve + postframe callback settle
    await tester.pumpAndSettle();
    expect(find.text('探 索'), findsOneWidget);
    expect(find.text('搜索城市、博物馆或艺术品'), findsOneWidget);
    expect(find.text('奥赛博物馆'), findsOneWidget);
    expect(find.text('卢浮宫'), findsOneWidget);
  });

  testWidgets('切换城市 chips 更新馆列表', (tester) async {
    await tester.pumpWidget(_wrap());
    await tester.pumpAndSettle();
    await tester.tap(find.text('阿姆斯特丹'));
    await tester.pumpAndSettle();
    expect(find.text('梵高博物馆'), findsOneWidget);
    expect(find.text('奥赛博物馆'), findsNothing);
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
}
