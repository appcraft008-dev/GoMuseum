/// explore_page_a1_smoke_test.dart
///
/// Smoke test: override museumsListProvider with fake data from 2 cities,
/// verify museum names render and city chips appear.
import 'package:flutter/material.dart';
import 'package:gomuseum_app/l10n/app_localizations.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gomuseum_app/features/content/data/models/museum_summary_model.dart';
import 'package:gomuseum_app/features/content/presentation/providers/catalog_providers.dart';
import 'package:gomuseum_app/features/explore/presentation/pages/explore_page.dart';

void main() {
  const fakeData = [
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
      slug: 'pompidou',
      name: '蓬皮杜中心',
      nameEn: '蓬皮杜中心',
      city: '巴黎',
      cityEn: '巴黎',
      country: 'FR',
      coordinates: [48.8607, 2.3522],
      artworkCount: 120,
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
          museumsListProvider.overrideWith((_) async => fakeData),
        ],
        child: const MaterialApp(
            localizationsDelegates: AppLocalizations.localizationsDelegates,
            supportedLocales: AppLocalizations.supportedLocales,
            locale: const Locale('zh'),
            home: Scaffold(body: ExplorePage())),
      );

  testWidgets('A1 smoke: 刊头渲染', (tester) async {
    await tester.pumpWidget(_wrap());
    await tester.pumpAndSettle();
    expect(find.text('探 索'), findsOneWidget);
  });

  testWidgets('A1 smoke: 博物馆名称渲染', (tester) async {
    await tester.pumpWidget(_wrap());
    await tester.pumpAndSettle();
    // default city = 巴黎 (first in list)
    expect(find.text('奥赛博物馆'), findsOneWidget);
    expect(find.text('蓬皮杜中心'), findsOneWidget);
  });

  testWidgets('A1 smoke: 城市 chips 由数据去重生成', (tester) async {
    await tester.pumpWidget(_wrap());
    await tester.pumpAndSettle();
    expect(find.text('巴黎'), findsWidgets); // chip + section header
    expect(
        find.text('阿姆斯特丹'), findsOneWidget); // chip only (not in current view)
  });

  testWidgets('A1 smoke: 切换城市 chip 显示另一城市博物馆', (tester) async {
    await tester.pumpWidget(_wrap());
    await tester.pumpAndSettle();
    await tester.tap(find.text('阿姆斯特丹'));
    await tester.pumpAndSettle();
    expect(find.text('梵高博物馆'), findsOneWidget);
    expect(find.text('奥赛博物馆'), findsNothing);
  });
}
