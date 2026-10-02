/// 足迹必须拉全 —— 原先只拉第一页 20 条且页面没有「加载更多」,
/// 2026-10-02 用户识别 160+ 条只看得到 20 件。
library;

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gomuseum_app/features/history/data/datasources/history_remote_datasource.dart';
import 'package:gomuseum_app/features/history/data/models/history_item_model.dart';
import 'package:gomuseum_app/features/history/presentation/providers/history_providers.dart';
import 'package:gomuseum_app/features/settings/presentation/providers/language_provider.dart';

/// 模拟后端分页:总共 [total] 条,按 offset/limit 切。
class _PagedDs implements HistoryRemoteDataSource {
  _PagedDs(this.total);
  final int total;
  int calls = 0;

  @override
  Future<List<HistoryItemModel>> getRecentHistory({
    int limit = 20,
    int offset = 0,
    int? days,
    String? language,
  }) async {
    calls++;
    final end = (offset + limit).clamp(0, total);
    return [
      for (var i = offset; i < end; i++)
        HistoryItemModel(
          id: 'e$i',
          artworkName: 'A$i',
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
  Future<void> deleteHistoryItem(String id) async {}
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
}
