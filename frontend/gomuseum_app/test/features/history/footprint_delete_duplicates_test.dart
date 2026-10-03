/// 足迹按「一次参观内同一件只列一次」去重后,删除必须连带删掉藏起来的重复条,
/// 否则删完旧的那条立刻顶上来,用户看到的是"删不掉"。
library;

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gomuseum_app/features/history/data/datasources/history_remote_datasource.dart';
import 'package:gomuseum_app/features/history/data/models/history_item_model.dart';
import 'package:gomuseum_app/features/history/presentation/providers/history_providers.dart';
import 'package:gomuseum_app/features/settings/presentation/providers/language_provider.dart';

HistoryItemModel _ev(String id, String qid, DateTime t,
        {String slug = 'orsay'}) =>
    HistoryItemModel(
      id: id,
      artworkName: qid,
      artist: '',
      period: '',
      description: '',
      confidence: 1,
      timestamp: t,
      museumSlug: slug,
      qid: qid,
    );

class _Ds implements HistoryRemoteDataSource {
  _Ds(this.items);
  final List<HistoryItemModel> items;
  final deleted = <String>[];

  @override
  Future<List<HistoryItemModel>> getRecentHistory({
    int limit = 20,
    int offset = 0,
    int? days,
    String? language,
  }) async =>
      items.skip(offset).take(limit).toList();

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
  Future<void> deleteHistoryItem(String id) async => deleted.add(id);
}

void main() {
  test('删一件 → 同一次参观里它的重复条一起删;别天的同一件不动', () async {
    final ds = _Ds([
      _ev('new', 'Q1', DateTime(2026, 10, 2, 12)),
      _ev('other', 'Q2', DateTime(2026, 10, 2, 11)),
      _ev('old', 'Q1', DateTime(2026, 10, 2, 10)),
      _ev('yesterday', 'Q1', DateTime(2026, 10, 1, 10)),
    ]);
    final c = ProviderContainer(overrides: [
      historyRemoteDataSourceProvider.overrideWithValue(ds),
      resolvedLocaleProvider.overrideWithValue(const Locale('zh')),
    ]);
    addTearDown(c.dispose);
    c.listen(historyProvider, (_, __) {});
    while (c.read(historyProvider).isLoading) {
      await Future<void>.delayed(Duration.zero);
    }

    await c.read(historyProvider.notifier).deleteItem('new');

    expect(ds.deleted.toSet(), {'new', 'old'});
    expect(
        c.read(historyProvider).items.map((i) => i.id), ['other', 'yesterday']);
  });
}
