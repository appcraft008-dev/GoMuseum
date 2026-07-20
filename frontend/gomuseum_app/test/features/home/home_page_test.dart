import 'dart:async';
import 'package:gomuseum_app/l10n/app_localizations.dart';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:go_router/go_router.dart';
import 'package:gomuseum_app/features/home/presentation/pages/home_page.dart';
import 'package:gomuseum_app/features/payment/domain/entities/user_benefits.dart';
import 'package:gomuseum_app/features/payment/presentation/providers/benefits_provider.dart';

class _FakeBenefitsState extends BenefitsState {
  @override
  FutureOr<UserBenefits> build() => const UserBenefits(
        hasAccess: true,
        recognitionQuota: 8,
        referralBonusQuota: 0,
        totalQuota: 8,
        isPremium: false,
        dayPassActive: false,
        totalUsed: 2,
      );
}

void main() {
  testWidgets('首页渲染刊头、门票 CTA、额度与博物馆卡片', (tester) async {
    await tester.pumpWidget(
      ProviderScope(
        overrides: [
          benefitsStateProvider.overrideWith(_FakeBenefitsState.new),
        ],
        child: const MaterialApp(
            localizationsDelegates: AppLocalizations.localizationsDelegates,
            supportedLocales: AppLocalizations.supportedLocales,
            locale: const Locale('zh'),
            home: Scaffold(body: HomePage())),
      ),
    );
    await tester.pump();

    expect(find.text('GOMUSEUM'), findsOneWidget);
    expect(find.text('走近一件作品，\n听懂它的故事。'), findsOneWidget);
    expect(find.text('拍照识别讲解'), findsOneWidget);
    expect(
      find.textContaining('免费识别还剩', findRichText: true),
      findsOneWidget,
    );
    expect(find.text('奥赛博物馆'), findsOneWidget);
    expect(find.text('01'), findsOneWidget);
    expect(find.text('附近博物馆'), findsOneWidget);
  });

  testWidgets('橘园卡片(无 topWorks,比奥赛矮)整个卡槽都可点击,不留死区', (tester) async {
    // 回归：橘园无 topWorks 行，卡片实际渲染高度比奥赛矮 ~60px，
    // 但卡槽固定 344px 高——此前只有卡片自身 GestureDetector 可点，
    // 卡片下方的卡槽留白点击无反应（真机反馈"点橘园没反应"的根因）。
    final router = GoRouter(routes: [
      GoRoute(path: '/', builder: (_, __) => const HomePage()),
      GoRoute(
          path: '/museum/:slug',
          builder: (c, s) =>
              Scaffold(body: Text('MUSEUM:${s.pathParameters['slug']}'))),
      GoRoute(path: '/camera', builder: (_, __) => const SizedBox()),
      GoRoute(path: '/explore', builder: (_, __) => const SizedBox()),
    ]);
    await tester.pumpWidget(
      ProviderScope(
        overrides: [
          benefitsStateProvider.overrideWith(_FakeBenefitsState.new),
        ],
        child: MaterialApp.router(
          routerConfig: router,
          localizationsDelegates: AppLocalizations.localizationsDelegates,
          supportedLocales: AppLocalizations.supportedLocales,
          locale: const Locale('zh'),
        ),
      ),
    );
    await tester.pump();

    final cardTopLeft = tester.getTopLeft(find
        .ancestor(of: find.text('橘园美术馆'), matching: find.byType(Container))
        .first);
    final cardSize = tester.getSize(find
        .ancestor(of: find.text('橘园美术馆'), matching: find.byType(Container))
        .first);
    // 卡片本体下方 30px 处点击（矮卡下方的卡槽留白区）。
    final belowCard = Offset(cardTopLeft.dx + cardSize.width / 2,
        cardTopLeft.dy + cardSize.height + 30);
    await tester.tapAt(belowCard);
    await tester.pumpAndSettle();

    expect(find.text('MUSEUM:orangerie'), findsOneWidget);
  });
}
