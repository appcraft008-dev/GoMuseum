import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gomuseum_app/features/explore/data/museum_pack.dart';
import 'package:gomuseum_app/features/explore/presentation/pages/explore_page.dart';

Widget _wrap() => ProviderScope(
      overrides: [
        // 避免测试发起真实网络请求（dio 超时 Timer 会泄漏）
        museumPackProvider.overrideWith(
          (ref, slug) async => const MuseumPack(
            slug: 'orsay',
            nameZh: '奥赛博物馆',
            cityZh: '巴黎',
            artworkCount: 60,
            artworks: [],
          ),
        ),
      ],
      child: const MaterialApp(home: Scaffold(body: ExplorePage())),
    );

void main() {
  testWidgets('渲染刊头、搜索框与默认城市馆列表', (tester) async {
    await tester.pumpWidget(_wrap());
    expect(find.text('探 索'), findsOneWidget);
    expect(find.text('搜索城市、博物馆或艺术品'), findsOneWidget);
    expect(find.text('奥赛博物馆'), findsOneWidget);
    expect(find.text('卢浮宫'), findsOneWidget);
  });

  testWidgets('切换城市 chips 更新馆列表', (tester) async {
    await tester.pumpWidget(_wrap());
    await tester.tap(find.text('阿姆斯特丹'));
    await tester.pump();
    expect(find.text('梵高博物馆'), findsOneWidget);
    expect(find.text('奥赛博物馆'), findsNothing);
  });

  testWidgets('搜索过滤博物馆', (tester) async {
    await tester.pumpWidget(_wrap());
    await tester.enterText(find.byType(TextField), '橘园');
    await tester.pump();
    expect(find.text('橘园美术馆'), findsOneWidget);
    expect(find.text('卢浮宫'), findsNothing);
  });
}
