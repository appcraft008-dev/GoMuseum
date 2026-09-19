/// 从足迹点进去,到底带了什么参数去讲解页。
///
/// 这条用**真的 HistoryPage + 真的 provider 链**跑,只把最外层 repository 换成
/// 假的。理由是本轮验收里学到的一课:拿自己搭的假组件断言,把被测代码原样改回
/// 错的照样绿 —— 必须渲染真页面。
library;

import 'package:dartz/dartz.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_localizations/flutter_localizations.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:go_router/go_router.dart';
import 'package:gomuseum_app/core/error/failures.dart';
import 'package:gomuseum_app/features/content/data/models/museum_summary_model.dart';
import 'package:gomuseum_app/features/content/presentation/providers/catalog_providers.dart';
import 'package:gomuseum_app/features/guide/presentation/pages/guide_page.dart';
import 'package:gomuseum_app/features/history/domain/entities/history_item.dart';
import 'package:gomuseum_app/features/history/domain/repositories/history_repository.dart';
import 'package:gomuseum_app/features/history/presentation/pages/history_page.dart';
import 'package:gomuseum_app/features/history/presentation/providers/history_providers.dart';
import 'package:gomuseum_app/l10n/app_localizations.dart';
import 'package:gomuseum_app/ui/gm/gm.dart';

class _FakeRepo implements HistoryRepository {
  _FakeRepo(this.items);
  final List<HistoryItem> items;

  @override
  Future<Either<Failure, List<HistoryItem>>> getRecentHistory({
    int limit = 20,
    int offset = 0,
    int? days,
  }) async =>
      Right(items);

  @override
  Future<Either<Failure, List<HistoryItem>>> searchHistory({
    required String query,
    int limit = 20,
  }) async =>
      Right(items);

  @override
  Future<Either<Failure, Map<String, dynamic>>> getHistoryStats({
    int days = 30,
  }) async =>
      const Right({});

  @override
  Future<Either<Failure, void>> deleteHistoryItem(String id) async =>
      const Right(null);
}

HistoryItem _item({String? slug, String? qid}) => HistoryItem(
      id: 'ev-1',
      artworkName: '蒙娜丽莎',
      artist: '达芬奇',
      period: '文艺复兴',
      description: '',
      confidence: 0.93,
      timestamp: DateTime(2026, 9, 5, 10, 30),
      museumSlug: slug,
      qid: qid,
    );

/// 渲染真的足迹页。返回的闭包读出"讲解页收到了什么参数"。
Future<GuideArgs? Function()> _pump(
    WidgetTester tester, List<HistoryItem> items) async {
  GuideArgs? captured;
  final router = GoRouter(
    initialLocation: '/history',
    routes: [
      GoRoute(
        path: '/history',
        builder: (_, __) => const Scaffold(body: HistoryPage()),
      ),
      GoRoute(
        path: '/guide',
        builder: (_, state) {
          captured = state.extra as GuideArgs?;
          return const Scaffold(body: Text('讲解页'));
        },
      ),
      GoRoute(path: '/camera', builder: (_, __) => const SizedBox()),
    ],
  );

  await tester.pumpWidget(
    ProviderScope(
      overrides: [
        historyRepositoryProvider.overrideWithValue(_FakeRepo(items)),
        // 足迹页现在要查馆名(按「一次参观」分组,见 footprint_visit.dart)。
        // 不覆写就是一次真 dio 请求,测试结束后超时 Timer 还挂着直接判失败。
        // 本组只关心点进去带了什么参数,给空列表即可(小节标题回落 slug)。
        museumsListProvider.overrideWith((ref) async => <MuseumSummary>[]),
      ],
      child: MaterialApp.router(
        routerConfig: router,
        localizationsDelegates: const [
          AppLocalizations.delegate,
          GlobalMaterialLocalizations.delegate,
          GlobalWidgetsLocalizations.delegate,
          GlobalCupertinoLocalizations.delegate,
        ],
        supportedLocales: AppLocalizations.supportedLocales,
      ),
    ),
  );
  return () => captured;
}

void main() {
  testWidgets('有 slug+qid 时走馆藏那条路,讲解页才有内容可拉', (tester) async {
    final peek = await _pump(tester, [_item(slug: 'louvre', qid: 'Q12418')]);
    await tester.pumpAndSettle();
    await tester.tap(find.text('蒙娜丽莎'));
    await tester.pumpAndSettle();

    final args = peek();
    expect(args, isNotNull, reason: '点了没跳转');
    expect(args!.slug, 'louvre');
    expect(args.qid, 'Q12418');
    // 走这条路时不该再塞 result:GuideArgs 两条路径二选一,
    // 混着传会让讲解页不知道该信哪个。
    expect(args.result, isNull);
  });

  testWidgets('老后端不给 slug/qid 时回落到 result,不能崩也不能不跳', (tester) async {
    final peek = await _pump(tester, [_item()]);
    await tester.pumpAndSettle();
    await tester.tap(find.text('蒙娜丽莎'));
    await tester.pumpAndSettle();

    final args = peek();
    expect(args, isNotNull);
    expect(args!.slug, isNull);
    expect(args.result, isNotNull);
    expect(args.result!.artworkName, '蒙娜丽莎');
  });

  testWidgets('艺术家为空时不留一个孤零零的分隔点', (tester) async {
    await _pump(tester, [
      HistoryItem(
        id: 'ev-2',
        artworkName: '蒙娜丽莎',
        artist: '', // 作者不详/富化没覆盖
        period: '',
        description: '',
        confidence: 0.9,
        timestamp: DateTime(2026, 9, 5, 10, 30),
      ),
    ]);
    await tester.pumpAndSettle();

    expect(find.text('10:30'), findsOneWidget);
    expect(find.text('10:30 · '), findsNothing);
  });

  testWidgets('有缩略图就要显示出来,不是永远一个灰块', (tester) async {
    // 后端 `_summary` 一直在返回 thumbnail,前端却写死 `image: null` ——
    // 数据在手里却不用,足迹页每条都是灰方块。
    await _pump(tester, [
      HistoryItem(
        id: 'ev-3',
        artworkName: '蒙娜丽莎',
        artist: '达芬奇',
        period: '',
        description: '',
        confidence: 0.9,
        timestamp: DateTime(2026, 9, 5, 10, 30),
        thumbnail: 'https://cdn.example/thumb.jpg',
      ),
    ]);
    await tester.pump();

    final thumb = tester.widget<GmThumb>(find.byType(GmThumb));
    expect(thumb.image, isA<NetworkImage>());
    expect((thumb.image! as NetworkImage).url, 'https://cdn.example/thumb.jpg');
    tester.takeException(); // 测试环境没有网络,图片加载失败与本用例无关
  });
}
