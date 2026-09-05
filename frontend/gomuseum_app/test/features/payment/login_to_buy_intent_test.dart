/// 「登录后购买」必须带上**转正意图**（`?upgrade=1`）。
///
/// 守卫的规则是「已登录还停在登录页 → 回首页」，游客也算已登录。没有这个
/// 标记，游客点「登录后购买」会被立刻弹回首页 —— 而通票挂账号、游客不许
/// 直接买，那个按钮是他买票的唯一入口，等于**游客永远买不了票**。
///
/// 这条测的是**导航参数**，不是守卫本身（守卫见 `test/core/router/`）：
/// 守卫改对了、入口忘了带参数，一样是买不了票，而且两边各自的测试都绿。
library;

import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:go_router/go_router.dart';
import 'package:gomuseum_app/core/router/app_router.dart';
import 'package:gomuseum_app/features/payment/data/entitlements.dart';
import 'package:gomuseum_app/features/payment/data/pass_history.dart';
import 'package:gomuseum_app/features/payment/data/pass_product.dart';
import 'package:gomuseum_app/features/payment/domain/entities/user_benefits.dart';
import 'package:gomuseum_app/features/payment/presentation/pages/benefits_page.dart';
import 'package:gomuseum_app/features/payment/presentation/providers/benefits_provider.dart';
import 'package:gomuseum_app/features/payment/presentation/widgets/paywall_sheet.dart';
import 'package:gomuseum_app/l10n/app_localizations.dart';

/// 游客的权益：能识别、**不能购买**（买票前必须登录）。
/// `canPurchase: false` 正是让按钮变成「登录后购买」的那一位。
const _guest = Entitlements(
  state: 'none',
  canPurchase: false,
  canRecognize: true,
  canAudioAny: false,
  freeRecognitionsLeft: 3,
  freeRecognitionsTotal: 5,
);

class _StubBenefits extends BenefitsState {
  @override
  FutureOr<UserBenefits> build() => UserBenefits.none();
}

void main() {
  testWidgets('游客点「登录后购买」→ 跳转必须带 ?upgrade=1', (t) async {
    t.view.physicalSize = const Size(360, 900);
    t.view.devicePixelRatio = 1.0;
    addTearDown(t.view.reset);

    String? landed;
    final router = GoRouter(
      initialLocation: '/benefits',
      routes: [
        GoRoute(path: '/benefits', builder: (_, __) => const BenefitsPage()),
        GoRoute(
          path: '/login',
          builder: (_, state) {
            landed = state.uri.toString();
            return const Scaffold(body: Text('登录页'));
          },
        ),
      ],
    );

    final container = ProviderContainer(overrides: [
      entitlementsProvider.overrideWith((ref) async => _guest),
      passHistoryProvider.overrideWith((ref) async => <PassRecord>[]),
      benefitsStateProvider.overrideWith(() => _StubBenefits()),
    ]);
    addTearDown(container.dispose);

    await t.pumpWidget(UncontrolledProviderScope(
      container: container,
      child: MaterialApp.router(
        routerConfig: router,
        localizationsDelegates: AppLocalizations.localizationsDelegates,
        supportedLocales: AppLocalizations.supportedLocales,
        locale: const Locale('zh'),
      ),
    ));
    await t.pumpAndSettle();

    final l10n = await AppLocalizations.delegate.load(const Locale('zh'));
    final cta = find.text(l10n.paywallLoginToBuy);
    expect(cta, findsOneWidget, reason: '游客权益下按钮该是「登录后购买」');

    await t.tap(cta);
    await t.pumpAndSettle();

    expect(landed, isNotNull, reason: '点了没跳转');
    expect(
      Uri.parse(landed!).queryParameters[kUpgradeParam],
      '1',
      reason: '没带转正意图 —— 守卫会把游客立刻弹回首页，票就永远买不成',
    );
  });

  testWidgets('讲解页付费墙点「登录后购买」→ 同样必须带 ?upgrade=1', (t) async {
    // 与权益页那条**分开测**：两个入口各写一次 push，改对一个漏掉另一个
    // 是这类 bug 最常见的形态（这次线上就是三个入口一起坏的）。
    t.view.physicalSize = const Size(360, 900);
    t.view.devicePixelRatio = 1.0;
    addTearDown(t.view.reset);

    String? landed;
    late BuildContext ctx;
    final router = GoRouter(
      initialLocation: '/x',
      routes: [
        GoRoute(
          path: '/x',
          builder: (c, __) {
            ctx = c;
            return const Scaffold(body: SizedBox());
          },
        ),
        GoRoute(
          path: '/login',
          builder: (_, state) {
            landed = state.uri.toString();
            return const Scaffold(body: Text('登录页'));
          },
        ),
      ],
    );

    await t.pumpWidget(ProviderScope(
      overrides: [
        entitlementsProvider.overrideWith((ref) async => _guest),
        passPriceProvider.overrideWith((ref) async => '€7.99'),
      ],
      child: MaterialApp.router(
        routerConfig: router,
        localizationsDelegates: AppLocalizations.localizationsDelegates,
        supportedLocales: AppLocalizations.supportedLocales,
        locale: const Locale('zh'),
      ),
    ));
    await t.pumpAndSettle();

    final l10n = await AppLocalizations.delegate.load(const Locale('zh'));
    showPaywallSheet(ctx, onBuy: () {});
    await t.pumpAndSettle();

    final cta = find.text(l10n.paywallLoginToBuy);
    expect(cta, findsOneWidget, reason: '游客权益下按钮该是「登录后购买」');
    await t.tap(cta);
    await t.pumpAndSettle();

    expect(landed, isNotNull, reason: '点了没跳转');
    expect(Uri.parse(landed!).queryParameters[kUpgradeParam], '1',
        reason: '付费墙这个入口漏了转正意图 —— 游客照样买不了票');
  });
}
