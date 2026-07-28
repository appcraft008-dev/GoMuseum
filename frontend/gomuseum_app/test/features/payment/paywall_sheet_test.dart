/// 付费墙内容:锁住三条**产品承诺**,不是锁像素。
///
/// 这三句话错了会直接变成差评或退款请求,所以值得测。
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gomuseum_app/features/payment/data/entitlements.dart';
import 'package:gomuseum_app/features/payment/presentation/widgets/paywall_sheet.dart';
import 'package:gomuseum_app/l10n/app_localizations.dart';

const _guest = Entitlements(
  state: 'not_purchased',
  canPurchase: false, // 游客:必须先登录才能买
  canRecognize: true,
  canAudioAny: false,
);
const _member = Entitlements(
  state: 'not_purchased',
  canPurchase: true,
  canRecognize: true,
  canAudioAny: false,
);

Widget _wrap(Widget child,
        {Locale locale = const Locale('zh'), Entitlements ent = _member}) =>
    ProviderScope(
      overrides: [
        entitlementsProvider.overrideWith((ref) async => ent),
      ],
      child: MaterialApp(
        locale: locale,
        localizationsDelegates: AppLocalizations.localizationsDelegates,
        supportedLocales: AppLocalizations.supportedLocales,
        home: Scaffold(body: child),
      ),
    );

void main() {
  testWidgets('说清"买了不立即计时" —— 旅游产品常提前几天买,不说会被投诉', (t) async {
    await t.pumpWidget(_wrap(const PaywallSheetContent()));
    await t.pumpAndSettle();
    expect(find.textContaining('不立即计时'), findsOneWidget);
  });

  testWidgets('说清"文字讲解始终免费" —— 付费墙在现场体验,不在内容', (t) async {
    await t.pumpWidget(_wrap(const PaywallSheetContent()));
    await t.pumpAndSettle();
    expect(find.textContaining('始终免费'), findsOneWidget);
  });

  testWidgets('购买与恢复购买都在 —— 缺恢复入口会被应用商店打回', (t) async {
    // 走真实的 sheet 路径:组件会 Navigator.pop 自己,直接塞进 Scaffold 会炸
    var bought = false;
    var restored = false;
    late BuildContext ctx;
    await t.pumpWidget(_wrap(Builder(builder: (c) {
      ctx = c;
      return const SizedBox();
    })));

    final l10n = await AppLocalizations.delegate.load(const Locale('zh'));

    showPaywallSheet(ctx, onRestore: () => restored = true);
    await t.pumpAndSettle();
    await t.tap(find.text(l10n.paywallRestore));
    await t.pumpAndSettle();
    expect(restored, isTrue);
    expect(find.text(l10n.paywallRestore), findsNothing, reason: '点完应关闭');

    showPaywallSheet(ctx, onBuy: () => bought = true);
    await t.pumpAndSettle();
    await t.tap(find.text(l10n.paywallBuy));
    await t.pumpAndSettle();
    expect(bought, isTrue);
  });

  testWidgets('游客看到的是「登录后购买」 —— 通票挂账号,游客买了换手机就拿不回', (t) async {
    await t.pumpWidget(_wrap(const PaywallSheetContent(), ent: _guest));
    await t.pumpAndSettle();
    final l10n = await AppLocalizations.delegate.load(const Locale('zh'));
    expect(find.text(l10n.paywallLoginToBuy), findsOneWidget);
    expect(find.text(l10n.paywallBuy), findsNothing);
    expect(find.text(l10n.paywallLoginWhy), findsOneWidget, reason: '要说清为什么');
  });

  testWidgets('已登录用户直接看到购买按钮', (t) async {
    await t.pumpWidget(_wrap(const PaywallSheetContent(), ent: _member));
    await t.pumpAndSettle();
    final l10n = await AppLocalizations.delegate.load(const Locale('zh'));
    expect(find.text(l10n.paywallBuy), findsOneWidget);
    expect(find.text(l10n.paywallLoginToBuy), findsNothing);
  });

  testWidgets('十种语言都不缺键(缺了会抛,不是显示英文)', (t) async {
    for (final locale in AppLocalizations.supportedLocales) {
      final l10n = await AppLocalizations.delegate.load(locale);
      for (final s in [
        l10n.paywallTitle,
        l10n.paywallPitch,
        l10n.paywallClockNote,
        l10n.paywallFreeAlways,
        l10n.paywallBuy,
        l10n.paywallRestore,
        l10n.audioFreePreview,
        l10n.audioLockedHint,
        l10n.quotaExhausted,
        l10n.activateTitle,
        l10n.activateBody,
        l10n.activateConfirm,
        l10n.activateLater,
        l10n.paywallLoginToBuy,
        l10n.paywallLoginWhy,
      ]) {
        expect(s.trim(), isNotEmpty, reason: '$locale 有空文案');
      }
    }
  });
}
