/// 足迹的显示语言必须跟**界面语言**走,不是跟"识别那一刻的语言"走。
///
/// 2026-09-20 用户截图报告:英文界面下,中文界面识别的那几件仍显示中文标题,
/// 同一屏里中英混排,切语言也不变。缺陷有两层,这个文件钉前端那层:
///
/// - 后端层:`history.py` 的 `_render` 拿 `ev.language`(识别当时的语言)当显示语言。
///   由 `test_history_footprints.py` 钉住。
/// - **前端层(本文件)**:请求根本不带 `language`;而且 `History` notifier 不 watch
///   语言,所以就算后端修好了,用户切完语言这一页也不会重新拉。
///   **只修其中一层,用户看到的现象不变** —— 所以两层各有测试。
library;

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:gomuseum_app/features/history/data/datasources/history_remote_datasource.dart';
import 'package:gomuseum_app/features/history/data/models/history_item_model.dart';
import 'package:gomuseum_app/features/history/presentation/providers/history_providers.dart';
import 'package:gomuseum_app/features/settings/presentation/providers/language_provider.dart';

/// 只记录每次请求收到的 language,不关心返回什么。
class _SpyDataSource implements HistoryRemoteDataSource {
  final List<String?> recentLangs = [];
  final List<String?> searchLangs = [];

  @override
  Future<List<HistoryItemModel>> getRecentHistory({
    int limit = 20,
    int offset = 0,
    int? days,
    String? language,
  }) async {
    recentLangs.add(language);
    return [];
  }

  @override
  Future<List<HistoryItemModel>> searchHistory({
    required String query,
    int limit = 20,
    String? language,
  }) async {
    searchLangs.add(language);
    return [];
  }

  @override
  Future<Map<String, dynamic>> getHistoryStats({int days = 30}) async => {};

  @override
  Future<void> deleteHistoryItem(String id) async {}
}

ProviderContainer _containerWith(_SpyDataSource spy, Locale? locale) {
  return ProviderContainer(
    overrides: [
      historyRemoteDataSourceProvider.overrideWithValue(spy),
      // 固定"生效语言",绕开设备 locale 解析 —— 本测试关心的是取值有没有
      // 传下去、变了会不会重拉,不是解析规则本身。
      resolvedLocaleProvider.overrideWithValue(locale ?? const Locale('en')),
    ],
  );
}

void main() {
  test('拉取足迹时带上界面语言', () async {
    final spy = _SpyDataSource();
    final c = _containerWith(spy, const Locale('zh'));
    addTearDown(c.dispose);

    c.read(historyProvider);
    await Future<void>.delayed(Duration.zero);

    expect(spy.recentLangs, ['zh']);
  });

  test('繁体中文要映射成后端的 zh-hant,不能发 zh', () {
    // 后端 zh 与 zh-hant 是两套内容。发错了,繁体用户会拿到简体标题 ——
    // 这正是 apiLanguage() 存在的理由,足迹这条路径不许绕过它。
    expect(
      apiLanguage(Locale.fromSubtags(languageCode: 'zh', scriptCode: 'Hant')),
      'zh-hant',
    );
  });

  test('搜索也带上界面语言 —— 用户搜的是他现在看到的那个名字', () async {
    final spy = _SpyDataSource();
    final c = _containerWith(spy, const Locale('fr'));
    addTearDown(c.dispose);

    await c.read(historyProvider.notifier).searchHistory('Mona');

    expect(spy.searchLangs, ['fr']);
  });

  test('切换语言会重新拉一遍足迹,并且带的是新语言', () async {
    // 🔑 这条钉的是 `build()` 里那句 `ref.watch(resolvedLocaleProvider)`。
    // 换成 `ref.read` 的话:第一次请求照样带语言、上面三条测试全绿,
    // 但切语言后列表不会重拉 —— 用户看到的缺陷原样还在。
    final spy = _SpyDataSource();
    final c = ProviderContainer(
      overrides: [
        historyRemoteDataSourceProvider.overrideWithValue(spy),
        resolvedLocaleProvider.overrideWith((ref) => ref.watch(_locale)),
      ],
    );
    addTearDown(c.dispose);

    // 用 listen 保持订阅 —— 只 read 的话 provider 会被回收,重建也就无从谈起
    c.listen(historyProvider, (_, __) {});
    await Future<void>.delayed(Duration.zero);
    expect(spy.recentLangs, ['zh']);

    c.read(_locale.notifier).state = const Locale('en');
    await Future<void>.delayed(Duration.zero);

    expect(spy.recentLangs, ['zh', 'en'], reason: '切语言必须重新拉一遍,且带的是切换后的语言');
  });
}

/// 供上面那条测试驱动语言变化。
final _locale = StateProvider<Locale>((ref) => const Locale('zh'));
