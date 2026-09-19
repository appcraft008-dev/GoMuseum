/// 足迹页把「一次参观」渲染成了什么。
///
/// 分组规则本身在 `footprint_visit_test.dart` 里纯测；这里管接线：
/// 馆名有没有真查出来、城市层该不该出现、日期文案有没有把参数写反。
/// 跟 `footprint_tap_test.dart` 一样渲染**真页面**——拿自建假组件断言，
/// 把被测代码改回错的照样绿。
library;

import 'dart:async';

import 'package:dartz/dartz.dart';
import 'package:flutter/material.dart';
import 'package:flutter_localizations/flutter_localizations.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gomuseum_app/core/error/failures.dart';
import 'package:gomuseum_app/features/content/data/models/museum_summary_model.dart';
import 'package:gomuseum_app/features/content/presentation/providers/catalog_providers.dart';
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

MuseumSummary _museum(String slug, String name, String city) => MuseumSummary(
      slug: slug,
      name: name,
      nameEn: '$slug-en',
      city: city,
      cityEn: '$city-en',
      country: 'FR',
      coordinates: const [],
      artworkCount: 1,
    );

HistoryItem _item(String name, DateTime t, {String? slug}) => HistoryItem(
      id: '$name@$t',
      artworkName: name,
      artist: '',
      period: '',
      description: '',
      confidence: 0.9,
      timestamp: t,
      museumSlug: slug,
      qid: 'Q1',
    );

Future<void> _pump(
  WidgetTester tester,
  List<HistoryItem> items, {
  List<MuseumSummary>? museums,
}) async {
  await tester.pumpWidget(
    ProviderScope(
      overrides: [
        historyRepositoryProvider.overrideWithValue(_FakeRepo(items)),
        // 必须覆写：不覆写就是一次真 dio 请求，测试结束后连接超时的 Timer
        // 还挂着，整个用例直接判失败。
        // museums == null = 模拟"馆列表还没回来"，用永不完成的 future
        // 而不是真请求，走 slug 兜底那条路。
        museumsListProvider.overrideWith(
          (ref) => museums == null
              ? Completer<List<MuseumSummary>>().future
              : Future.value(museums),
        ),
      ],
      child: MaterialApp(
        locale: const Locale('zh'),
        localizationsDelegates: const [
          AppLocalizations.delegate,
          GlobalMaterialLocalizations.delegate,
          GlobalWidgetsLocalizations.delegate,
          GlobalCupertinoLocalizations.delegate,
        ],
        supportedLocales: AppLocalizations.supportedLocales,
        home: const Scaffold(body: HistoryPage()),
      ),
    ),
  );
  await tester.pumpAndSettle();
}

List<String> _sectionLabels(WidgetTester t) => t
    .widgetList<GmSectionHead>(find.byType(GmSectionHead))
    .map((w) => w.label)
    .toList();

void main() {
  final paris = [
    _museum('orsay', '奥赛博物馆', '巴黎'),
    _museum('orangerie', '橘园美术馆', '巴黎'),
  ];

  testWidgets('同一天两个馆 → 两个小节，标题是馆名不是 slug', (t) async {
    await _pump(
      t,
      [
        _item('舞女', DateTime(2026, 9, 18, 10), slug: 'orsay'),
        _item('睡莲', DateTime(2026, 9, 18, 15), slug: 'orangerie'),
      ],
      museums: paris,
    );

    expect(_sectionLabels(t), ['橘园美术馆', '奥赛博物馆'], reason: '应按时间倒序，且显示馆名');
    expect(find.text('orsay'), findsNothing, reason: 'slug 漏到界面上了');
  });

  testWidgets('小节备注带日期和件数 —— 「什么时候看了几件」', (t) async {
    final today = DateTime.now();
    await _pump(
      t,
      [
        _item('a', DateTime(today.year, today.month, today.day, 10),
            slug: 'orsay'),
        _item('b', DateTime(today.year, today.month, today.day, 11),
            slug: 'orsay'),
      ],
      museums: paris,
    );

    final note = t.widget<GmSectionHead>(find.byType(GmSectionHead)).note ?? '';
    expect(note, contains('今天'));
    expect(note, contains('2 件'));
  });

  testWidgets('🔴 四个馆全在巴黎 → 不画城市层（恒定一组的层级只是白占缩进）', (t) async {
    await _pump(
      t,
      [
        _item('舞女', DateTime(2026, 9, 18, 10), slug: 'orsay'),
        _item('睡莲', DateTime(2026, 9, 18, 15), slug: 'orangerie'),
      ],
      museums: paris,
    );

    expect(find.text('巴黎'), findsNothing);
  });

  testWidgets('跨城 → 城市层出现，且不打乱倒序时间线（对照组）', (t) async {
    // 少了这条，一个"永远不画城市"的实现也能让上一条全绿。
    // 巴黎 → 阿姆斯特丹 → 巴黎：城市标题按时间线出现三次，
    // 而不是把两段巴黎收拢成一个文件夹（那会毁掉倒序时间线）。
    await _pump(
      t,
      [
        _item('新巴黎', DateTime(2026, 9, 18), slug: 'orsay'),
        _item('阿城', DateTime(2026, 8, 10), slug: 'rijks'),
        _item('旧巴黎', DateTime(2026, 7, 1), slug: 'louvre'),
      ],
      museums: [
        ...paris,
        _museum('rijks', '国立博物馆', '阿姆斯特丹'),
        _museum('louvre', '卢浮宫', '巴黎'),
      ],
    );

    expect(find.text('巴黎'), findsNWidgets(2), reason: '两段巴黎被收拢成一个文件夹了');
    expect(find.text('阿姆斯特丹'), findsOneWidget);
    expect(_sectionLabels(t), ['奥赛博物馆', '国立博物馆', '卢浮宫']);
  });

  testWidgets('馆列表还没回来 → 回落 slug，足迹照样列出来', (t) async {
    // 足迹不该被另一个请求卡住变空白。
    await _pump(t, [_item('舞女', DateTime(2026, 9, 18), slug: 'orsay')]);

    expect(find.text('舞女'), findsOneWidget);
    expect(_sectionLabels(t), ['orsay']);
  });

  testWidgets('老事件没有 museum_slug → 归到「未记录场馆」，不消失', (t) async {
    await _pump(
      t,
      [_item('老条目', DateTime(2026, 9, 18))],
      museums: paris,
    );

    expect(find.text('老条目'), findsOneWidget);
    expect(_sectionLabels(t), ['未记录场馆']);
  });

  testWidgets('🔴 跨年日期文案参数顺序 —— 写反了编译照过，只在屏幕上错', (t) async {
    // gen-l10n 把 `{month}/{day}/{year}` 重排成了形参 (day, month, year)，
    // 而三个形参全是 `Object`。写成 (year, month, day) 会渲染出「9年18月2026日」。
    final zh = await AppLocalizations.delegate.load(const Locale('zh'));
    expect(zh.dateYearMonthDay(18, 9, 2026), '2026年9月18日');

    final en = await AppLocalizations.delegate.load(const Locale('en'));
    expect(en.dateYearMonthDay(18, 9, 2026), '9/18/2026');
  });

  testWidgets('去年的足迹显示年份，今年的不显示', (t) async {
    final now = DateTime.now();
    await _pump(
      t,
      [
        _item('今年', DateTime(now.year, 1, 2, 10), slug: 'orsay'),
        _item('去年', DateTime(now.year - 1, 1, 2, 10), slug: 'orsay'),
      ],
      museums: paris,
    );

    final notes = t
        .widgetList<GmSectionHead>(find.byType(GmSectionHead))
        .map((w) => w.note ?? '')
        .toList();
    expect(notes.length, 2, reason: '跨年同月同日被并组了');
    expect(notes.any((n) => n.contains('${now.year - 1}年')), isTrue);
    expect(notes.any((n) => n.contains('${now.year}年')), isFalse,
        reason: '今年的不该带年份，多余');
  });
}
