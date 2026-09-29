/// 馆相关缓存必须随账号失效(2026-09-29 真机实测)。
///
/// 隐身馆只对预览账号可见(后端可见性闸按账号判)。用预览账号浏览过国立博物馆,
/// 切成普通账号/游客后,馆列表/藏品/讲解仍从缓存里原样显示 —— nginx 日志证实
/// 切换后**一个请求都没发**,后端的闸根本没机会拦。
///
/// 每个 provider 两格都要:同一账号内命中缓存(缓存本身是对的,要保留),
/// 换了账号就重拉。只测后一格的话,一个"每次都重拉"的实现也会绿。
library;

import 'dart:ui' show Locale;

import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gomuseum_app/features/auth/data/auth_repository.dart';
import 'package:gomuseum_app/features/auth/domain/user.dart';
import 'package:gomuseum_app/features/auth/presentation/auth_provider.dart';
import 'package:gomuseum_app/features/content/presentation/providers/catalog_providers.dart';
import 'package:gomuseum_app/features/explore/data/museum_pack.dart';
import 'package:gomuseum_app/features/recognition/presentation/providers/recognition_providers.dart'
    as recog;
import 'package:gomuseum_app/features/search/data/search_api.dart';
import 'package:gomuseum_app/features/settings/presentation/providers/language_provider.dart';

User _user(String id) => User(
      id: id,
      email: '$id@example.com',
      isActive: true,
      isVerified: true,
      createdAt: DateTime(2026, 1, 1),
    );

class _Repo extends AuthRepository {
  _Repo(this.current) : super(Dio());

  final User current;

  @override
  Future<User?> getCurrentUser() async => current;

  @override
  Future<User> login(String email, String password) async => _user(email);
}

/// 只数请求次数;一律失败 —— 我们关心的是"有没有再去拉",不是结果。
Dio _countingDio(void Function(String path) onCall) => Dio()
  ..interceptors.add(InterceptorsWrapper(
    onRequest: (options, handler) {
      onCall(options.path);
      handler.reject(DioException(requestOptions: options));
    },
  ));

Future<void> _drain(Future<Object?> f) async {
  try {
    await f;
  } catch (_) {}
}

void main() {
  final cases = <String, ProviderListenable<AsyncValue<Object?>>>{
    '馆列表': museumsListProvider,
    '馆详情': museumDetailProvider((slug: 'rijksmuseum', language: 'zh')),
    '讲解': objectContentProvider((slug: 'rijksmuseum', qid: 'Q219831')),
    '搜索': searchProvider((slug: null, q: 'rijks', lang: 'zh')),
    '馆包': museumPackProvider('rijksmuseum'),
  };

  for (final c in cases.entries) {
    test('${c.key}:同账号命中缓存,换账号重拉', () async {
      var calls = 0;
      final dio = _countingDio((_) => calls++);
      final container = ProviderContainer(overrides: [
        // ⚠️ App 里有两个 dioProvider(auth 的与 recognition 生成的),搜索/馆包走后者
        dioProvider.overrideWithValue(dio),
        recog.dioProvider.overrideWithValue(dio),
        resolvedLocaleProvider.overrideWithValue(const Locale('zh')),
        currentUserProvider
            .overrideWith((ref) => AuthNotifier(_Repo(_user('preview')))),
      ]);
      addTearDown(container.dispose);

      container.read(currentUserProvider);
      while (container.read(currentUserProvider).valueOrNull == null) {
        await Future<void>.delayed(Duration.zero);
      }

      // autoDispose 的那几个要有人听着才驻留
      final sub = container.listen(c.value, (_, __) {});
      addTearDown(sub.close);
      Future<void> settle() async {
        // 真实时间片:dio 拦截器链不全在微任务里,只转微任务的话部分请求还没发出去
        for (var i = 0; i < 20; i++) {
          await Future<void>.delayed(const Duration(milliseconds: 5));
        }
      }

      await settle();
      final afterA = calls;
      expect(afterA, greaterThan(0));

      container.read(c.value); // 再读:同账号应命中缓存
      await settle();
      expect(calls, afterA, reason: '同一账号内应命中缓存');

      await container.read(currentUserProvider.notifier).login('guest', 'pw');
      await _drain(Future<void>.value());
      await settle();
      expect(calls, greaterThan(afterA), reason: '换了账号却没重拉 —— 预览账号看过的隐身馆会留给游客');
    });
  }
}
