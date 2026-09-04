/// 删号弹窗必须**事前**说清「已购通票一并作废且拿不回」。
///
/// 后端 `AuthService.delete_user_account` 会把 entitlement 置 revoked、user_id
/// 换成墓碑值;而通票是消耗型商品,验证成功即被 Google 消耗 —— `restorePurchases`
/// 之后永远回放不出来,重装重注册也只能再买一次。而弹窗原本只说「删除账号资料与
/// **剩余额度**」,只字未提通票。撞契约 I20:没收已付款项必须事前披露。
///
/// 三组样本缺一不可:有票要说、**读不到也要说**(I21:读不到 ≠ 没有)、
/// 确定没票才不说。少了最后一组,一个"永远都说"的实现也能过前两组。
library;

import 'dart:async';

import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'package:gomuseum_app/features/auth/data/auth_repository.dart';
import 'package:gomuseum_app/features/auth/domain/user.dart';
import 'package:gomuseum_app/features/auth/presentation/auth_provider.dart';
import 'package:gomuseum_app/features/payment/data/entitlements.dart';
import 'package:gomuseum_app/features/payment/domain/entities/user_benefits.dart';
import 'package:gomuseum_app/features/payment/presentation/providers/benefits_provider.dart';
import 'package:gomuseum_app/features/settings/presentation/pages/settings_page.dart';
import 'package:gomuseum_app/l10n/app_localizations.dart';

const _noPass = Entitlements(
  state: 'not_purchased',
  canPurchase: true,
  canRecognize: true,
  canAudioAny: false,
  freeRecognitionsLeft: 3,
  freeRecognitionsTotal: 5,
);
const _active = Entitlements(
  state: 'active',
  canPurchase: false,
  canRecognize: true,
  canAudioAny: true,
);
const _unactivated = Entitlements(
  state: 'purchased_not_activated',
  canPurchase: false,
  canRecognize: true,
  canAudioAny: false,
);

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  Future<AppLocalizations> openDialog(WidgetTester t, Entitlements ent) async {
    SharedPreferences.setMockInitialValues({});
    final container = ProviderContainer(overrides: [
      currentUserProvider
          .overrideWith((ref) => _LoggedIn(AuthRepository(Dio()))),
      benefitsStateProvider.overrideWith(() => _StubBenefits()),
      entitlementsProvider.overrideWith((ref) async => ent),
    ]);
    addTearDown(container.dispose);

    await t.pumpWidget(UncontrolledProviderScope(
      container: container,
      child: const MaterialApp(
        localizationsDelegates: AppLocalizations.localizationsDelegates,
        supportedLocales: AppLocalizations.supportedLocales,
        locale: Locale('zh'),
        home: Scaffold(body: SettingsPage()),
      ),
    ));
    await t.pumpAndSettle();

    final l10n = await AppLocalizations.delegate.load(const Locale('zh'));
    // 「删除账号」在设置页最底下,不同权益态页面长度不同 —— 有的态里它落在
    // 屏幕外,直接 tap 会**静默打空**(只警告不报错),弹窗根本没开,
    // 后面的断言就全变成"没找到披露"的假通过。
    await t.ensureVisible(find.text(l10n.deleteAccount));
    await t.pumpAndSettle();
    await t.tap(find.text(l10n.deleteAccount));
    await t.pumpAndSettle();
    expect(find.text(l10n.deleteAccountQ), findsOneWidget,
        reason: '弹窗没打开,下面的断言就都是假的');
    return l10n;
  }

  testWidgets('通票生效中:必须点名通票会作废', (t) async {
    final l10n = await openDialog(t, _active);
    expect(find.textContaining(l10n.deleteAccountBodyPass), findsOneWidget);
  });

  testWidgets('已购未激活:同样要说 —— 钱一样付过了', (t) async {
    final l10n = await openDialog(t, _unactivated);
    expect(find.textContaining(l10n.deleteAccountBodyPass), findsOneWidget);
  });

  testWidgets('权益读不到时也要说 —— 读不到不等于没有(I21)', (t) async {
    final l10n = await openDialog(t, Entitlements.unknown);
    expect(find.textContaining(l10n.deleteAccountBodyPass), findsOneWidget,
        reason: '离线时对一个刚买完票的人漏说,他会以为只是删掉一个空账号');
  });

  testWidgets('确定没买过:不说 —— 否则吓唬一个没花过钱的人', (t) async {
    final l10n = await openDialog(t, _noPass);
    expect(find.textContaining(l10n.deleteAccountBodyPass), findsNothing);
    expect(find.textContaining(l10n.deleteAccountBody), findsOneWidget);
  });

  testWidgets('十种语言都有这句披露(缺了会抛,不是显示英文)', (t) async {
    for (final locale in AppLocalizations.supportedLocales) {
      final l10n = await AppLocalizations.delegate.load(locale);
      expect(l10n.deleteAccountBodyPass.trim(), isNotEmpty,
          reason: '$locale 缺少通票作废披露');
    }
  });
}

class _LoggedIn extends AuthNotifier {
  _LoggedIn(super.repository) {
    state = AsyncValue.data(User(
      id: 'u1',
      email: 'someone@example.com',
      username: 'someone',
      isActive: true,
      isVerified: true,
      createdAt: DateTime.utc(2026, 9, 1),
    ));
  }
}

class _StubBenefits extends BenefitsState {
  @override
  FutureOr<UserBenefits> build() => UserBenefits.none();
}
