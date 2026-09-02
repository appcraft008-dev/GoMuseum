// test/features/settings/pass_status_card_test.dart
//
// 设置页顶部那张卡在**已购**时必须换内容:显示通票状态,按钮从「升级」变「查看权益」。
//
// 为什么值得一个测试:通票生效期间后端把 free_recognitions_left/total 返回 **null**
// (不限次)。照免费层的写法渲染,已付费用户看到的是「免费识别额度 —/0」+ 一个
// 「升级」按钮 —— 付了钱,App 从头到尾没有一处告诉他票在手上,点按钮还被送回商店。
// 这类"状态对了但没表达出来"的洞,后端断言全都是绿的(2026-09-02 用户提出)。
import 'dart:async';

import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'package:gomuseum_app/features/auth/data/auth_repository.dart';
import 'package:gomuseum_app/features/auth/presentation/auth_provider.dart';
import 'package:gomuseum_app/features/payment/data/entitlements.dart';
import 'package:gomuseum_app/features/payment/domain/entities/user_benefits.dart';
import 'package:gomuseum_app/features/payment/presentation/providers/benefits_provider.dart';
import 'package:gomuseum_app/features/settings/presentation/pages/settings_page.dart';
import 'package:gomuseum_app/l10n/app_localizations.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  Future<void> pumpWith(WidgetTester tester, Entitlements ent) async {
    SharedPreferences.setMockInitialValues({});
    final container = ProviderContainer(
      overrides: [
        currentUserProvider
            .overrideWith((ref) => _StubAuthNotifier(AuthRepository(Dio()))),
        benefitsStateProvider.overrideWith(() => _StubBenefitsState()),
        entitlementsProvider.overrideWith((ref) async => ent),
      ],
    );
    addTearDown(container.dispose);

    await tester.pumpWidget(
      UncontrolledProviderScope(
        container: container,
        child: const MaterialApp(
          localizationsDelegates: AppLocalizations.localizationsDelegates,
          supportedLocales: AppLocalizations.supportedLocales,
          locale: Locale('zh'),
          home: Scaffold(body: SettingsPage()),
        ),
      ),
    );
    await tester.pumpAndSettle();
  }

  testWidgets('通票生效中:显示状态与到期,按钮是「查看权益」', (tester) async {
    await pumpWith(
      tester,
      Entitlements(
        state: 'active',
        canPurchase: true,
        canRecognize: true,
        canAudioAny: true,
        expiresAt: DateTime.utc(2026, 9, 9, 14, 37),
        // 通票期间后端就是返回 null —— 这正是老代码渲染成 "—/0" 的输入。
        freeRecognitionsLeft: null,
        freeRecognitionsTotal: null,
      ),
    );

    expect(find.text('通票生效中'), findsOneWidget);
    expect(find.text('查看权益'), findsOneWidget);
    expect(find.text('升级'), findsNothing);
    // 免费额度那套文案不该再出现
    expect(find.text('免费识别额度'), findsNothing);
  });

  testWidgets('已购未激活:提示待激活,按钮同样不是「升级」', (tester) async {
    await pumpWith(
      tester,
      const Entitlements(
        state: 'purchased_not_activated',
        canPurchase: true,
        canRecognize: true,
        canAudioAny: false,
      ),
    );

    expect(find.text('已购买 · 待激活'), findsOneWidget);
    expect(find.text('首次播放讲解时开始计时'), findsOneWidget);
    expect(find.text('升级'), findsNothing);
  });

  testWidgets('未购买:仍是免费额度卡 + 「升级」', (tester) async {
    await pumpWith(
      tester,
      const Entitlements(
        state: 'not_purchased',
        canPurchase: true,
        canRecognize: true,
        canAudioAny: false,
        freeRecognitionsLeft: 3,
        freeRecognitionsTotal: 5,
      ),
    );

    expect(find.text('免费识别额度'), findsOneWidget);
    expect(find.text('剩余 3/5 次'), findsOneWidget);
    expect(find.text('升级'), findsOneWidget);
    expect(find.text('查看权益'), findsNothing);
  });
}

class _StubAuthNotifier extends AuthNotifier {
  _StubAuthNotifier(super.repository) {
    state = const AsyncValue.data(null);
  }
}

class _StubBenefitsState extends BenefitsState {
  @override
  FutureOr<UserBenefits> build() => UserBenefits.none();
}
