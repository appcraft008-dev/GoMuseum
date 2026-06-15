import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
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
        child: const MaterialApp(home: Scaffold(body: HomePage())),
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
}
