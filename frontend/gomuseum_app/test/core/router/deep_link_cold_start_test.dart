/// App Links 冷启动走真路由(spec 2026-09-20-share-web-pages-design §六)。
///
/// auth_guard_test 只测纯函数;这里钉的是它**接上真路由之后**的时序:
/// 系统把链接当初始路由交给 App → 登录态还在 loading(user=null)→ 守卫弹去
/// `/login?from=…` → 登录态就绪 → 守卫再跑 → 必须落在那件作品的讲解页,不是首页。
/// 任何一环(路由没注册 / from 没带 / 刷新没接 / 路径参数名写错)断了都会红。
library;

import 'dart:async';

import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gomuseum_app/core/router/app_router.dart';
import 'package:gomuseum_app/features/auth/data/auth_repository.dart';
import 'package:gomuseum_app/features/auth/domain/user.dart';
import 'package:gomuseum_app/features/auth/presentation/auth_provider.dart';
import 'package:gomuseum_app/features/auth/presentation/login_page.dart';
import 'package:gomuseum_app/features/content/data/models/object_content_model.dart';
import 'package:gomuseum_app/features/content/data/models/object_list_model.dart';
import 'package:gomuseum_app/features/content/presentation/providers/catalog_providers.dart';
import 'package:gomuseum_app/features/guide/presentation/pages/guide_page.dart';
import 'package:gomuseum_app/features/payment/data/entitlements.dart';
import 'package:gomuseum_app/l10n/app_localizations.dart';
import 'package:gomuseum_app/theme/app_theme.dart';

/// 登录态由测试手动放行,模拟冷启动时的 loading。
class _SlowRepo extends AuthRepository {
  _SlowRepo(this._gate) : super(Dio());
  final Completer<User?> _gate;

  @override
  Future<User?> getCurrentUser() => _gate.future;
}

final _guest = User(
  id: 'g1',
  email: null,
  isActive: true,
  isVerified: false,
  isGuest: true,
  createdAt: DateTime(2026, 9, 29),
);

void main() {
  testWidgets('冷启动点链接:登录态 loading 时去登录页,就绪后回到那件作品', (t) async {
    const link = '/a/orsay/Q1?lang=zh&s=app';
    // 安卓冷启动给的是**完整 URL**(引擎 intent.getData().toString())。
    // 早先这里喂的是裸路径 —— 模拟了一个平台从不产生的输入,测试绿、真机红(V42)。
    t.binding.platformDispatcher.defaultRouteNameTestValue =
        'https://gomuseum.app$link';
    addTearDown(t.binding.platformDispatcher.clearDefaultRouteNameTestValue);

    final gate = Completer<User?>();
    final container = ProviderContainer(overrides: [
      authRepositoryProvider.overrideWithValue(_SlowRepo(gate)),
      objectContentProvider((slug: 'orsay', qid: 'Q1'))
          .overrideWith((ref) => const ObjectContent(
                qid: 'Q1',
                category: 'painting',
                language: 'zh',
                status: ContentStatus.ready,
                title: '草地上的午餐',
                images: [],
                facts: ObjectFacts(),
                tabs: [],
                suggestedQuestions: [],
              )),
      entitlementsProvider.overrideWith((ref) async => Entitlements.unknown),
      museumEntitlementsProvider
          .overrideWith((ref, _) async => Entitlements.unknown),
    ]);
    addTearDown(container.dispose);
    final router = container.read(goRouterProvider);

    await t.pumpWidget(UncontrolledProviderScope(
      container: container,
      child: MaterialApp.router(
        routerConfig: router,
        localizationsDelegates: AppLocalizations.localizationsDelegates,
        supportedLocales: AppLocalizations.supportedLocales,
        locale: const Locale('zh'),
        theme: AppTheme.lightTheme(),
      ),
    ));
    await t.pump();

    // ① loading 中:被弹去登录页,且原目标跟着走
    final at = router.routerDelegate.currentConfiguration.uri;
    expect(at.path, '/login');
    expect(at.queryParameters['from'], link);
    expect(find.byType(LoginPage), findsOneWidget);

    // ② 登录态就绪(游客)→ 守卫再跑 → 回到那件作品,不是首页
    gate.complete(_guest);
    await t.pumpAndSettle();
    expect(router.routerDelegate.currentConfiguration.uri.toString(), link);
    final page = t.widget<GuidePage>(find.byType(GuidePage));
    expect(page.args.slug, 'orsay');
    expect(page.args.qid, 'Q1');
  });
}
