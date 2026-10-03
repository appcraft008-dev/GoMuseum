/// 权益请求必须带**界面语言** —— 票名/范围名/馆名都由后端按 `language` 给,
/// 不带就落到后端默认 zh:英法界面的「我的通票」整页中文(2026-10-03 真机截图,
/// 「巴黎 7 日通票」「卢浮宫, 橘园美术馆…」「购买记录」三处)。
library;

import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gomuseum_app/features/auth/presentation/auth_provider.dart';
import 'package:gomuseum_app/features/payment/data/entitlements.dart';
import 'package:gomuseum_app/features/settings/presentation/providers/language_provider.dart';

final _locale = StateProvider<Locale>((ref) => const Locale('fr'));

/// 只记录请求的 query,不发真请求(失败走 Entitlements.unknown)。
Dio _spyDio(List<Map<String, dynamic>> seen) => Dio()
  ..interceptors.add(InterceptorsWrapper(onRequest: (o, h) {
    seen.add(o.queryParameters);
    h.reject(DioException(requestOptions: o));
  }));

ProviderContainer _container(List<Map<String, dynamic>> seen) {
  final c = ProviderContainer(overrides: [
    dioProvider.overrideWithValue(_spyDio(seen)),
    resolvedLocaleProvider.overrideWith((ref) => ref.watch(_locale)),
  ]);
  addTearDown(c.dispose);
  return c;
}

void main() {
  test('全局权益带界面语言;繁体发 zh-hant', () async {
    final seen = <Map<String, dynamic>>[];
    final c = _container(seen);
    c.listen(entitlementsProvider, (_, __) {});
    await c.read(entitlementsProvider.future);
    expect(seen.last['language'], 'fr');

    // 切语言必须重拉,否则切完还是旧语言的票名
    c.read(_locale.notifier).state =
        const Locale.fromSubtags(languageCode: 'zh', scriptCode: 'Hant');
    await c.read(entitlementsProvider.future);
    expect(seen.last['language'], 'zh-hant');
  });

  test('馆内权益也带界面语言(与 museum 并存)', () async {
    final seen = <Map<String, dynamic>>[];
    final c = _container(seen);
    c.listen(museumEntitlementsProvider('louvre'), (_, __) {});
    await c.read(museumEntitlementsProvider('louvre').future);
    expect(seen.last, {'museum': 'louvre', 'language': 'fr'});
  });
}
