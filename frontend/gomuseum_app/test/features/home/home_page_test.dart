import 'dart:async';
import 'package:gomuseum_app/l10n/app_localizations.dart';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:go_router/go_router.dart';
import 'package:gomuseum_app/features/content/data/models/museum_summary_model.dart';
import 'package:gomuseum_app/features/content/presentation/providers/catalog_providers.dart';
import 'package:gomuseum_app/features/home/presentation/pages/home_page.dart';
import 'package:gomuseum_app/features/payment/domain/entities/user_benefits.dart';
import 'package:gomuseum_app/features/payment/data/entitlements.dart';
import 'package:gomuseum_app/features/payment/presentation/providers/benefits_provider.dart';

/// 首页馆卡片走 A1 GET /museums(2026-07-26 API 化),测试注入假馆列表。
MuseumSummary _m(String slug, String name, {int count = 100}) => MuseumSummary(
      slug: slug,
      name: name,
      nameEn: slug,
      city: '巴黎',
      cityEn: 'Paris',
      country: 'FR',
      coordinates: const [],
      artworkCount: count,
    );

final _fakeMuseums = [
  _m('orsay', '奥赛博物馆', count: 6789),
  _m('orangerie', '橘园美术馆', count: 140),
  _m('louvre', '卢浮宫', count: 17283),
];

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

/// 首页额度行读 /entitlements/me;不打桩就会真发请求(测试里表现为 pending timer)
const _fakeEntitlements = Entitlements(
  state: 'not_purchased',
  canRecognize: true,
  canAudioAny: false,
  canAiAsk: false,
  freeRecognitionsLeft: 8,
  freeRecognitionsTotal: 5,
);

void main() {
  testWidgets('首页渲染刊头、门票 CTA、额度与博物馆卡片', (tester) async {
    await tester.pumpWidget(
      ProviderScope(
        overrides: [
          benefitsStateProvider.overrideWith(_FakeBenefitsState.new),
          entitlementsProvider.overrideWith((ref) async => _fakeEntitlements),
          museumsListProvider.overrideWith((_) async => _fakeMuseums),
        ],
        child: const MaterialApp(
            localizationsDelegates: AppLocalizations.localizationsDelegates,
            supportedLocales: AppLocalizations.supportedLocales,
            locale: const Locale('zh'),
            home: Scaffold(body: HomePage())),
      ),
    );
    await tester.pump();
    await tester.pump(); // FutureProvider 落地

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
          entitlementsProvider.overrideWith((ref) async => _fakeEntitlements),
          museumsListProvider.overrideWith((_) async => _fakeMuseums),
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
    await tester.pump(); // FutureProvider 落地

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

  testWidgets('新上线馆(卢浮宫)自动出现在首页且可点进馆(API 化收益)', (tester) async {
    // 回归:此前首页馆列表硬编码,卢浮宫卡片写死且无 slug → 上线后点不动。
    // 改走 A1 GET /museums 后,后端上新馆前端零改动自动可用。
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
          entitlementsProvider.overrideWith((ref) async => _fakeEntitlements),
          museumsListProvider.overrideWith((_) async => _fakeMuseums),
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
    await tester.pump();

    await tester.dragUntilVisible(
        find.text('卢浮宫'), find.byType(ListView).first, const Offset(-300, 0));
    await tester.pumpAndSettle();
    await tester.tap(find.text('卢浮宫'));
    await tester.pumpAndSettle();

    expect(find.text('MUSEUM:louvre'), findsOneWidget);
  });
}
