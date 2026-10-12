/// 足迹必须拉全 —— 原先只拉第一页 20 条且页面没有「加载更多」,
/// 2026-10-02 用户识别 160+ 条只看得到 20 件。
/// 10-11:801 条足迹串行 9 个请求、全程转圈 4–5 秒 → 首个请求只拉 50 条立刻显示,
/// 其余后台续拉接在后面。
library;

import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gomuseum_app/features/history/data/datasources/history_remote_datasource.dart';
import 'package:gomuseum_app/features/history/data/models/history_item_model.dart';
import 'package:gomuseum_app/features/history/presentation/providers/history_providers.dart';
import 'package:gomuseum_app/features/settings/presentation/providers/language_provider.dart';

/// 模拟后端分页:总共 [total] 条,按 offset/limit 切。
class _PagedDs implements HistoryRemoteDataSource {
  _PagedDs(int total) : ids = [for (var i = 0; i < total; i++) 'e$i'];

  /// 服务端现存的足迹(删了就真少一条,后面的 offset 跟着前移)。
  final List<String> ids;
  int calls = 0;
  final limits = <int>[];

  /// 非空时,第一页之后的请求都等它放行(模拟后台续拉还没回来)。
  Completer<void>? gate;

  @override
  Future<List<HistoryItemModel>> getRecentHistory({
    int limit = 20,
    int offset = 0,
    int? days,
    String? language,
  }) async {
    calls++;
    limits.add(limit);
    if (offset > 0 && gate != null) await gate!.future;
    final end = (offset + limit).clamp(0, ids.length);
    return [
      for (final id in ids.sublist(offset.clamp(0, ids.length), end))
        HistoryItemModel(
          id: id,
          artworkName: id,
          artist: '',
          period: '',
          description: '',
          confidence: 1,
          timestamp: DateTime(2026, 10, 2),
        ),
    ];
  }

  @override
  Future<List<HistoryItemModel>> searchHistory({
    required String query,
    int limit = 20,
    String? language,
  }) async =>
      [];

  @override
  Future<Map<String, dynamic>> getHistoryStats({int days = 30}) async => {};

  @override
  Future<void> deleteHistoryItem(String id) async => ids.remove(id);
}

Future<HistoryState> _loaded(_PagedDs ds) async {
  final c = ProviderContainer(overrides: [
    historyRemoteDataSourceProvider.overrideWithValue(ds),
    resolvedLocaleProvider.overrideWithValue(const Locale('zh')),
  ]);
  addTearDown(c.dispose);
  c.listen(historyProvider, (_, __) {});
  for (var i = 0; i < 20 && c.read(historyProvider).isLoading; i++) {
    await Future<void>.delayed(Duration.zero);
  }
  return c.read(historyProvider);
}

void main() {
  test('164 条全部拉回来,不止第一页', () async {
    final s = await _loaded(_PagedDs(164));
    expect(s.items.length, 164);
    expect(s.items.map((i) => i.id).toSet().length, 164, reason: '不重不漏');
  });

  test('恰好整页时也能停下(多拉一次空页)', () async {
    final ds = _PagedDs(100);
    final s = await _loaded(ds);
    expect(s.items.length, 100);
    expect(ds.calls, lessThanOrEqualTo(2));
  });

  /// 切 tab = 页面卸载、没人再 listen。原先 autoDispose 会把整份足迹扔掉,
  /// 切回来从空列表重拉三页、全程转圈约 2 秒(2026-10-05 真机)。
  test('切走再切回不重拉', () async {
    final ds = _PagedDs(164);
    final c = ProviderContainer(overrides: [
      historyRemoteDataSourceProvider.overrideWithValue(ds),
      resolvedLocaleProvider.overrideWithValue(const Locale('zh')),
    ]);
    addTearDown(c.dispose);
    final sub = c.listen(historyProvider, (_, __) {});
    for (var i = 0; i < 20 && c.read(historyProvider).isLoading; i++) {
      await Future<void>.delayed(Duration.zero);
    }
    final calls = ds.calls;
    sub.close();
    for (var i = 0; i < 5; i++) {
      await Future<void>.delayed(Duration.zero);
    }
    c.listen(historyProvider, (_, __) {});
    await Future<void>.delayed(Duration.zero);
    expect(c.read(historyProvider).items.length, 164);
    expect(ds.calls, calls);
  });

  test('首个请求只拉 50 条,拿到就显示,不等后面的页', () async {
    final ds = _PagedDs(164)..gate = Completer<void>();
    final c = ProviderContainer(overrides: [
      historyRemoteDataSourceProvider.overrideWithValue(ds),
      resolvedLocaleProvider.overrideWithValue(const Locale('zh')),
    ]);
    addTearDown(c.dispose);
    c.listen(historyProvider, (_, __) {});
    for (var i = 0; i < 10; i++) {
      await Future<void>.delayed(Duration.zero);
    }
    expect(ds.limits.first, 50);
    final s = c.read(historyProvider);
    expect(s.items.length, 50);
    expect(s.hasMore, isTrue, reason: '还在续拉,统计行据此暂不显示');

    ds.gate!.complete();
    for (var i = 0; i < 20 && c.read(historyProvider).isLoading; i++) {
      await Future<void>.delayed(Duration.zero);
    }
    expect(c.read(historyProvider).items.length, 164);
    expect(c.read(historyProvider).hasMore, isFalse);
  });

  test('已有列表时刷新不先缩回 50 条', () async {
    final ds = _PagedDs(164);
    final c = ProviderContainer(overrides: [
      historyRemoteDataSourceProvider.overrideWithValue(ds),
      resolvedLocaleProvider.overrideWithValue(const Locale('zh')),
    ]);
    addTearDown(c.dispose);
    c.listen(historyProvider, (_, __) {});
    for (var i = 0; i < 20 && c.read(historyProvider).isLoading; i++) {
      await Future<void>.delayed(Duration.zero);
    }
    ds.gate = Completer<void>();
    final done = c.read(historyProvider.notifier).refresh();
    for (var i = 0; i < 10; i++) {
      await Future<void>.delayed(Duration.zero);
    }
    expect(c.read(historyProvider).items.length, 164);
    ds.gate!.complete();
    await done;
    expect(c.read(historyProvider).items.length, 164);
  });

  test('新一次加载开始后,旧的续拉结果作废', () async {
    final ds = _PagedDs(164)..gate = Completer<void>();
    final c = ProviderContainer(overrides: [
      historyRemoteDataSourceProvider.overrideWithValue(ds),
      resolvedLocaleProvider.overrideWithValue(const Locale('zh')),
    ]);
    addTearDown(c.dispose);
    c.listen(historyProvider, (_, __) {});
    for (var i = 0; i < 10; i++) {
      await Future<void>.delayed(Duration.zero);
    }
    final second = c.read(historyProvider.notifier).refresh();
    ds.gate!.complete();
    await second;
    for (var i = 0; i < 10; i++) {
      await Future<void>.delayed(Duration.zero);
    }
    final s = c.read(historyProvider);
    expect(s.items.length, 164);
    expect(s.items.map((i) => i.id).toSet().length, 164, reason: '两轮没有叠在一起');
  });

  test('续拉途中删一条:不复活、后面的也不漏', () async {
    final ds = _PagedDs(164)..gate = Completer<void>();
    final c = ProviderContainer(overrides: [
      historyRemoteDataSourceProvider.overrideWithValue(ds),
      resolvedLocaleProvider.overrideWithValue(const Locale('zh')),
    ]);
    addTearDown(c.dispose);
    c.listen(historyProvider, (_, __) {});
    for (var i = 0; i < 10; i++) {
      await Future<void>.delayed(Duration.zero);
    }
    expect(c.read(historyProvider).items.length, 50);
    await c.read(historyProvider.notifier).deleteItem('e3');
    ds.gate!.complete();
    for (var i = 0; i < 100 && c.read(historyProvider).isLoading; i++) {
      await Future<void>.delayed(Duration.zero);
    }
    final got = c.read(historyProvider).items.map((i) => i.id).toList();
    expect(got, isNot(contains('e3')));
    expect(got.toSet(), {for (var i = 0; i < 164; i++) 'e$i'}..remove('e3'));
  });

  /// 10-12 统计:识别后整份重拉占全部 API 请求 37%、一天 53.5MB → 只拉最新一页插到前面。
  test('识别后只拉最新一页,新条目插到最前', () async {
    final ds = _PagedDs(164);
    final c = ProviderContainer(overrides: [
      historyRemoteDataSourceProvider.overrideWithValue(ds),
      resolvedLocaleProvider.overrideWithValue(const Locale('zh')),
    ]);
    addTearDown(c.dispose);
    c.listen(historyProvider, (_, __) {});
    for (var i = 0; i < 20 && c.read(historyProvider).isLoading; i++) {
      await Future<void>.delayed(Duration.zero);
    }
    ds.ids.insert(0, 'new');
    ds.calls = 0;
    ds.limits.clear();
    await c.read(historyProvider.notifier).pullLatest();
    expect(ds.calls, 1);
    expect(ds.limits.single, lessThanOrEqualTo(20));
    final ids = c.read(historyProvider).items.map((i) => i.id).toList();
    expect(ids.first, 'new');
    expect(ids.length, 165);
    expect(ids.toSet().length, 165, reason: '已有的不重复插入');
  });

  test('列表还在加载时 pullLatest 走整份加载(不和续拉错位)', () async {
    final ds = _PagedDs(164)..gate = Completer<void>();
    final c = ProviderContainer(overrides: [
      historyRemoteDataSourceProvider.overrideWithValue(ds),
      resolvedLocaleProvider.overrideWithValue(const Locale('zh')),
    ]);
    addTearDown(c.dispose);
    c.listen(historyProvider, (_, __) {});
    for (var i = 0; i < 10; i++) {
      await Future<void>.delayed(Duration.zero);
    }
    ds.ids.insert(0, 'new');
    final done = c.read(historyProvider.notifier).pullLatest();
    ds.gate!.complete();
    await done;
    final ids = c.read(historyProvider).items.map((i) => i.id).toList();
    expect(ids.first, 'new');
    expect(ids.toSet().length, 165);
    expect(ids.length, 165);
  });
}
