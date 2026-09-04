/// 权益页四态:锁的是**每一态该给什么**,不是像素。
///
/// 这一页出过一次真金白银的事故:已付费用户进来看到的还是商店,以为没买成功
/// 而重复购买(2026-09-02 真机)。所以"已购之后不再出现购买按钮"是这里
/// 最该钉死的一条。
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gomuseum_app/features/payment/data/entitlements.dart';
import 'package:gomuseum_app/features/payment/data/pass_history.dart';
import 'package:gomuseum_app/features/payment/data/pass_product.dart';
import 'package:gomuseum_app/features/payment/presentation/pages/benefits_page.dart';
import 'package:gomuseum_app/l10n/app_localizations.dart';
import 'package:gomuseum_app/theme/app_theme.dart';

const _free = Entitlements(
  state: 'not_purchased',
  canPurchase: true,
  canRecognize: true,
  canAudioAny: false,
  freeRecognitionsLeft: 2,
  freeRecognitionsTotal: 5,
);

final _unactivated = Entitlements(
  state: 'purchased_not_activated',
  canPurchase: true,
  canRecognize: true,
  canAudioAny: false,
  activateBy: DateTime(2026, 10, 3, 14, 32),
);

final _active = Entitlements(
  state: 'active',
  canPurchase: true,
  canRecognize: true,
  canAudioAny: true,
  expiresAt: DateTime.now().add(const Duration(days: 4)),
);

const _expired = Entitlements(
  state: 'expired',
  canPurchase: true,
  canRecognize: true,
  canAudioAny: false,
  freeRecognitionsLeft: 5,
  freeRecognitionsTotal: 5,
);

final _usedUpPass = PassRecord(
  productId: 'paris_pass_7d',
  state: 'expired',
  purchasedAt: DateTime(2026, 8, 20, 9),
  activatedAt: DateTime(2026, 8, 20, 14, 32),
  expiresAt: DateTime(2026, 8, 27, 14, 32),
);

Widget _wrap(
  Entitlements ent, {
  List<PassRecord> history = const [],
  Locale locale = const Locale('zh'),
}) =>
    ProviderScope(
      overrides: [
        entitlementsProvider.overrideWith((ref) async => ent),
        passHistoryProvider.overrideWith((ref) async => history),
        // 真的 IAP 插件在测试环境不可用
        passPriceProvider.overrideWith((ref) async => '€7.99'),
      ],
      child: MaterialApp(
        locale: locale,
        localizationsDelegates: AppLocalizations.localizationsDelegates,
        supportedLocales: AppLocalizations.supportedLocales,
        theme: AppTheme.lightTheme(),
        home: const BenefitsPage(),
      ),
    );

Future<AppLocalizations> _l10n() =>
    AppLocalizations.delegate.load(const Locale('zh'));

/// ⚠️ 页面是 ListView,**默认只构建可见项** —— 默认 800×600 的测试视口下
/// 底部的 CTA 压根不在 widget 树里,find 会报"没找到"而不是"位置不对"。
/// 给一个够高的视口,让四态的内容一次全渲染出来。
Future<void> _pump(WidgetTester t, Widget app) async {
  t.view.physicalSize = const Size(1200, 4000);
  t.view.devicePixelRatio = 1.0;
  addTearDown(t.view.reset);
  await t.pumpWidget(app);
  await t.pumpAndSettle();
}

void main() {
  testWidgets('未购:显示购买按钮,额度按「已用/总数」算', (t) async {
    await _pump(t, _wrap(_free));
    final l10n = await _l10n();
    expect(find.text(l10n.paywallBuy), findsOneWidget);
    // 后端给的是**剩余** 2/5 → 已用是 3,不能把剩余画成已用
    expect(find.text('3 / 5'), findsOneWidget);
  });

  testWidgets('⭐ 已购未激活:绝不再出现购买按钮 —— 这是重复购买事故的根因', (t) async {
    await _pump(t, _wrap(_unactivated));
    final l10n = await _l10n();
    expect(find.text(l10n.paywallBuy), findsNothing);
    expect(find.text(l10n.paywallLoginToBuy), findsNothing);
    expect(find.text(l10n.benefitsStartNow), findsOneWidget);
    expect(find.text(l10n.benefitsMyPass), findsOneWidget, reason: '标题不再是商店');
  });

  testWidgets('已购未激活:说清 30 天不激活会失效 —— 后端真会没收', (t) async {
    await _pump(t, _wrap(_unactivated));
    expect(find.textContaining('30 天失效'), findsOneWidget);
  });

  testWidgets('生效中:识别显示「不限次」而不是次数,且没有购买按钮', (t) async {
    await _pump(t, _wrap(_active));
    final l10n = await _l10n();
    expect(find.text(l10n.unlimited), findsOneWidget);
    expect(find.text(l10n.paywallBuy), findsNothing);
    expect(find.text(l10n.ticketValidUntil), findsOneWidget);
  });

  testWidgets('生效中:有购买记录时列出日期,但**不显示金额**', (t) async {
    await _pump(t, _wrap(_active, history: [_usedUpPass]));
    final l10n = await _l10n();
    expect(find.text(l10n.benefitsSecPurchases), findsOneWidget);
    // 留字不留数:票面写「已付」,但不写金额 —— €7.99 是**现在的售价**,
    // 不是当时付的价(后端 amount 恒 NULL,不能拿现价顶替)
    expect(find.text(l10n.ticketPaid), findsOneWidget);
    expect(find.textContaining('€7.99'), findsNothing);
  });

  testWidgets('已到期:给用过的那张票 + 「再来一张」,不是一个空商店', (t) async {
    await _pump(t, _wrap(_expired, history: [_usedUpPass]));
    final l10n = await _l10n();
    expect(find.text(l10n.benefitsSecBuyAnother), findsOneWidget);
    expect(find.text(l10n.benefitsEndedAt), findsOneWidget);
    expect(find.text(l10n.paywallBuy), findsOneWidget, reason: '可以续购');
  });

  // 真机实测:作废票和下面在售的那张并排放着像双胞胎 —— 撕线和褪色在这套
  // 暖纸配色里几乎产生不了对比(饱和度本来就只有个位数,没什么可减的)。
  // 断的是"有没有一个正向标记",不是"有没有褪色":褪色测不出来,这正是问题所在。
  testWidgets('已到期:票上必须有作废戳 —— 光靠褪色在这套配色里看不出来', (t) async {
    await _pump(t, _wrap(_expired, history: [_usedUpPass]));
    final l10n = await _l10n();
    expect(find.text(l10n.ticketVoid), findsOneWidget);
  });

  testWidgets('在售的票不许盖作废戳', (t) async {
    await _pump(t, _wrap(_free));
    final l10n = await _l10n();
    expect(find.text(l10n.ticketVoid), findsNothing);
  });

  testWidgets('已到期但历史读不到:退回未购态,不编一张票出来', (t) async {
    await _pump(t, _wrap(_expired));
    final l10n = await _l10n();
    expect(find.text(l10n.benefitsEndedAt), findsNothing);
    expect(find.text(l10n.paywallBuy), findsOneWidget);
  });

  testWidgets('权益读不到:给重试,绝不说「登录后购买」,也不给购买入口', (t) async {
    await _pump(t, _wrap(Entitlements.unknown));
    final l10n = await _l10n();
    expect(find.text(l10n.edgeUnknownHead), findsOneWidget);
    expect(find.text(l10n.retry), findsOneWidget);
    expect(find.text(l10n.paywallLoginToBuy), findsNothing);
    expect(find.text(l10n.paywallBuy), findsNothing);
  });

  testWidgets('收据冲突页必须给出一个能真正联系上人的地址,不能是「即将推出」', (t) async {
    // 票面不显示对方邮箱(隐私),用户很可能不知道该登哪个账号 ——
    // 没有这条出口他就彻底卡住。设计明确说这是必需出口,不是装饰。
    final l10n = await _l10n();
    expect(kSupportEmail, contains('@'));
    expect(l10n.edgeSupportCopied(kSupportEmail), contains(kSupportEmail));
  });

  testWidgets('十种语言都不缺键(缺了会抛,不是显示英文)', (t) async {
    final d = DateTime(2026, 9, 10, 14, 32);
    for (final locale in AppLocalizations.supportedLocales) {
      final l10n = await AppLocalizations.delegate.load(locale);
      for (final s in [
        l10n.benefitsMyPass,
        l10n.benefitsSecFreeQuota,
        l10n.benefitsSecFeatures,
        l10n.benefitsSecBuyable,
        l10n.benefitsSecIncluded,
        l10n.benefitsSecUnlocked,
        l10n.benefitsSecPurchases,
        l10n.benefitsSecCurrentQuota,
        l10n.benefitsSecBuyAnother,
        l10n.benefitsRecognition,
        l10n.benefitsFreeAudioNote,
        l10n.benefitsFeatBrowse,
        l10n.benefitsFeatPresetQa,
        l10n.benefitsFeatRecognition,
        l10n.benefitsFeatAllAudio,
        l10n.benefitsFeatDeepAudio,
        l10n.benefitsNeedsPass,
        l10n.benefitsNotStartedHead,
        l10n.benefitsNotStartedBody,
        l10n.benefitsMuseums,
        l10n.benefitsStartNow,
        l10n.benefitsStartNowNote,
        l10n.benefitsExpiredBody,
        l10n.benefitsPrevPass(d, d),
        l10n.benefitsEndedAt,
        l10n.ticketPaid,
        l10n.benefitsDateOnly(d),
        l10n.edgeUnknownHead,
        l10n.edgeUnknownBody,
        l10n.edgeUnknownNote,
        l10n.edgeSeeFree,
        l10n.edgeSignedOutHead,
        l10n.edgeSignedOutBody,
        l10n.edgeConflictTitle,
        l10n.edgeConflictBody,
        l10n.edgeConflictBound,
        l10n.edgeConflictOther,
        l10n.edgeConflictHelp,
        l10n.edgeSwitchAccount,
        l10n.edgeContactSupport,
        l10n.edgeSupportCopied('a@b.c'),
        l10n.drawerLockedHint,
        l10n.drawerLockedCta,
        l10n.purchaseSuccess,
        l10n.purchaseFailed,
        l10n.purchaseVerifyPending,
      ]) {
        expect(s.trim(), isNotEmpty, reason: '$locale 有空文案');
      }
    }
  });
}
