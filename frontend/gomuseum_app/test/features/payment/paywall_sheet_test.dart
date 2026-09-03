/// 付费墙内容:锁住**产品承诺**和**票据状态机**,不是锁像素。
///
/// 这几句话错了会直接变成差评或退款请求,所以值得测。
import 'dart:typed_data';

import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gomuseum_app/features/auth/presentation/auth_provider.dart';
import 'package:gomuseum_app/features/payment/data/entitlements.dart';
import 'package:gomuseum_app/features/payment/data/pass_product.dart';
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

/// 让 `/entitlements/activate` 立刻失败:测激活失败分支时不能等真实网络
/// (等不到,pump 的假时钟推不动真 I/O)。
class _FailingAdapter implements HttpClientAdapter {
  @override
  Future<ResponseBody> fetch(RequestOptions options, Stream<Uint8List>? _,
          Future<void>? __) async =>
      ResponseBody.fromString('{}', 503);

  @override
  void close({bool force = false}) {}
}

Widget _wrap(
  Widget child, {
  Locale locale = const Locale('zh'),
  Entitlements ent = _member,
  String? price = '€7.99',
}) =>
    ProviderScope(
      overrides: [
        entitlementsProvider.overrideWith((ref) async => ent),
        // 真的 IAP 插件在测试环境不可用,价格由这里给
        passPriceProvider.overrideWith((ref) async => price),
        dioProvider
            .overrideWithValue(Dio()..httpClientAdapter = _FailingAdapter()),
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
    expect(find.textContaining('不马上开始计时'), findsOneWidget);
  });

  testWidgets('说清"文字讲解始终免费" —— 付费墙在现场体验,不在内容', (t) async {
    await t.pumpWidget(_wrap(const PaywallSheetContent()));
    await t.pumpAndSettle();
    expect(find.textContaining('始终免费'), findsOneWidget);
  });

  testWidgets('说清"未激活会失效" —— 后端真会没收,不告知就是偷偷吃票', (t) async {
    // ⚠️ 这条与后端 ACTIVATION_WINDOW 成对存在。删了这句 = 没披露就没收
    // 已付的款(Play 合规问题),删了那段代码 = 票面印了个假承诺。
    await t.pumpWidget(_wrap(const PaywallSheetContent()));
    await t.pumpAndSettle();
    expect(find.textContaining('30 天失效'), findsOneWidget);
  });

  testWidgets('显示价格 —— 此前弹层里根本没有价格,用户不知道多少钱就在点购买', (t) async {
    await t.pumpWidget(_wrap(const PaywallSheetContent()));
    await t.pumpAndSettle();
    expect(find.text('€7.99'), findsOneWidget);
  });

  testWidgets('拿不到价格就不显示 —— 宁可不显示,也不显示一个当地是错的金额', (t) async {
    await t.pumpWidget(_wrap(const PaywallSheetContent(), price: null));
    await t.pumpAndSettle();
    final l10n = await AppLocalizations.delegate.load(const Locale('zh'));
    expect(find.text(l10n.paywallPriceNote), findsNothing);
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

    showPaywallSheet(ctx, onBuy: () {}, onRestore: () => restored = true);
    await t.pumpAndSettle();
    await t.tap(find.text(l10n.paywallRestore));
    await t.pumpAndSettle();
    expect(restored, isTrue);
    expect(find.text(l10n.paywallRestore), findsNothing, reason: '点完应关闭');

    showPaywallSheet(ctx, onBuy: () => bought = true, onRestore: () {});
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
    expect(find.text(l10n.edgeSignedOutHead), findsOneWidget, reason: '要说清为什么');
    expect(find.text(l10n.edgeSignedOutBody), findsOneWidget);
  });

  testWidgets('权益读不到时绝不说「登录后购买」 —— 用户可能已登录,只是断网了', (t) async {
    // ⚠️ Entitlements.unknown 的 canPurchase 也是 false。少了 known 标记,
    // 这里就会对着一个已登录的用户要求登录 —— 他照做也没用。
    await t.pumpWidget(
        _wrap(const PaywallSheetContent(), ent: Entitlements.unknown));
    await t.pumpAndSettle();
    final l10n = await AppLocalizations.delegate.load(const Locale('zh'));
    expect(find.text(l10n.paywallLoginToBuy), findsNothing);
    expect(find.text(l10n.edgeUnknownHead), findsOneWidget);
    expect(find.text(l10n.retry), findsOneWidget, reason: '给重试,不给购买');
    expect(find.text(l10n.paywallBuy), findsNothing,
        reason: '读不到已有权益就买 = 诱导重复购买');
  });

  testWidgets('已登录用户直接看到购买按钮', (t) async {
    await t.pumpWidget(_wrap(const PaywallSheetContent(), ent: _member));
    await t.pumpAndSettle();
    final l10n = await AppLocalizations.delegate.load(const Locale('zh'));
    expect(find.text(l10n.paywallBuy), findsOneWidget);
    expect(find.text(l10n.paywallLoginToBuy), findsNothing);
  });

  // ── 激活确认:票在后端确认成功之前**必须完整** ──
  //
  // 这是整个票据隐喻的承重点。撕开 = 7×24 小时开始烧,画早了等于骗人:
  // 用户看到票撕了、以为计时开始,而后端根本没激活(或反过来)。

  testWidgets('确认页:说清不可撤销,存根位是空的(到期日待填)', (t) async {
    await t.pumpWidget(_wrap(const ActivatePassSheet()));
    await t.pumpAndSettle();
    final l10n = await AppLocalizations.delegate.load(const Locale('zh'));
    expect(find.text(l10n.activateTear), findsOneWidget);
    expect(find.text(l10n.ticketStubPending), findsOneWidget);
    expect(find.textContaining('不可撤销'), findsOneWidget);
    // 已购之后**留字不留数**:显示「已付」但不显示金额 —— 唯一能拿到的
    // 数字是商店当前售价,而那不是用户当时付的钱(见 GmTicketFace.paidLabel)
    expect(find.text(l10n.ticketPaid), findsOneWidget);
    expect(find.text('€7.99'), findsNothing);
  });

  testWidgets('后端确认失败:明说票没被使用,可重试 —— 不能让用户以为钱白花了', (t) async {
    // activatePass 走 dio,测试环境必然失败 → 正好覆盖失败分支
    await t.pumpWidget(_wrap(const ActivatePassSheet()));
    await t.pumpAndSettle();
    final l10n = await AppLocalizations.delegate.load(const Locale('zh'));

    await t.tap(find.text(l10n.activateTear));
    // ⚠️ 不能用 pumpAndSettle:等待态那颗转圈是无限动画,永远"settle"不了。
    await t.pump();
    for (var i = 0;
        i < 60 && find.text(l10n.activateFailTitle).evaluate().isEmpty;
        i++) {
      await t.pump(const Duration(milliseconds: 100));
    }

    expect(find.text(l10n.activateFailTitle), findsOneWidget);
    expect(find.text(l10n.activateRetry), findsOneWidget);
    // 票没撕开:存根位仍是"未撕开",不是到期日
    expect(find.text(l10n.ticketStubUntorn), findsOneWidget);
  });

  testWidgets('十种语言都不缺键(缺了会抛,不是显示英文)', (t) async {
    final now = DateTime(2026, 9, 10, 14, 32);
    for (final locale in AppLocalizations.supportedLocales) {
      final l10n = await AppLocalizations.delegate.load(locale);
      for (final s in [
        l10n.paywallTitle,
        l10n.paywallPitch,
        l10n.paywallPriceNote,
        l10n.paywallClockHead,
        l10n.paywallClockBody,
        l10n.paywallLapseNote,
        l10n.ticketPaid,
        l10n.paywallFreeAlways,
        l10n.paywallBuy,
        l10n.paywallRestore,
        l10n.audioFreePreview,
        l10n.audioLockedHint,
        l10n.quotaExhausted,
        l10n.paywallLoginToBuy,
        l10n.paywallLoginWhy,
        l10n.ticketStub,
        l10n.ticketStubPending,
        l10n.ticketStubUntorn,
        l10n.ticketValidUntil,
        l10n.ticketDateTime(now, now),
        l10n.ticketDaysLeft(7),
        l10n.activateSheetTitle,
        l10n.activateSheetBody(now, now),
        l10n.activateTear,
        l10n.activateLater,
        l10n.activateWaiting,
        l10n.activateWaitingNote,
        l10n.activateDoneTitle,
        l10n.activateDoneBody,
        l10n.activateDoneCta,
        l10n.activateFailTitle,
        l10n.activateFailBody,
        l10n.activateRetry,
      ]) {
        expect(s.trim(), isNotEmpty, reason: '$locale 有空文案');
      }
    }
  });
}
