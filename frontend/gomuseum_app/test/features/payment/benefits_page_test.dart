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
import 'package:gomuseum_app/features/payment/data/pass_offer.dart';
import 'package:gomuseum_app/features/payment/data/pass_product.dart';
import 'package:gomuseum_app/features/payment/presentation/pages/benefits_page.dart';
import 'package:gomuseum_app/l10n/app_localizations.dart';
import 'package:gomuseum_app/theme/app_theme.dart';

// 票的展示数据全部来自后端(offers/passes)—— 前端不认识任何一张具体的票
const _paris = PassOffer(
    productId: 'paris_pass_7d', days: 7, label: '巴黎', covers: ['卢浮宫', '奥赛博物馆']);
const _nl =
    PassOffer(productId: 'nl_pass_7d', days: 7, label: '荷兰', covers: ['国立博物馆']);

const _free = Entitlements(
  state: 'not_purchased',
  canPurchase: true,
  canRecognize: true,
  canAudioAny: false,
  freeRecognitionsLeft: 2,
  freeRecognitionsTotal: 5,
  offers: [_paris],
);

final _unactivated = Entitlements(
  state: 'purchased_not_activated',
  canPurchase: true,
  canRecognize: true,
  canAudioAny: false,
  activateBy: DateTime(2026, 10, 3, 14, 32),
  offers: const [_paris],
  passes: const [
    OwnedPass(
        productId: 'paris_pass_7d',
        label: '巴黎',
        days: 7,
        state: 'purchased_not_activated'),
  ],
);

final _active = Entitlements(
  state: 'active',
  canPurchase: true,
  canRecognize: true,
  canAudioAny: true,
  expiresAt: DateTime.now().add(const Duration(days: 4)),
  offers: const [_paris],
  passes: const [
    OwnedPass(
        productId: 'paris_pass_7d', label: '巴黎', days: 7, state: 'active'),
  ],
);

const _expired = Entitlements(
  state: 'expired',
  canPurchase: true,
  canRecognize: true,
  canAudioAny: false,
  freeRecognitionsLeft: 5,
  freeRecognitionsTotal: 5,
  offers: [_paris],
);

/// 买了从没激活、30 天窗口过了作废 —— activated_at / expires_at 都是 null。
final _lapsedPass = PassRecord(
  productId: 'paris_pass_7d',
  state: 'expired',
  purchasedAt: DateTime(2026, 8, 4, 10, 25),
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
  String? passId,
}) =>
    ProviderScope(
      overrides: [
        entitlementsProvider.overrideWith((ref) async => ent),
        passHistoryProvider.overrideWith((ref) async => history),
        // 真的 IAP 插件在测试环境不可用
        passPriceProvider.overrideWith((ref, _) async => '€7.99'),
      ],
      child: MaterialApp(
        locale: locale,
        localizationsDelegates: AppLocalizations.localizationsDelegates,
        supportedLocales: AppLocalizations.supportedLocales,
        theme: AppTheme.lightTheme(),
        home: BenefitsPage(passId: passId),
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
  testWidgets('⭐ 未购:额度与设置页**同一口径**(剩余),不是已用', (t) async {
    await _pump(t, _wrap(_free));
    final l10n = await _l10n();
    expect(find.text(l10n.paywallBuy), findsOneWidget);
    // 🔴 这条原本断言 '3 / 5'(已用)。设置页同一时刻显示「剩余 2/5 次」——
    // 同一个账号、同一秒,两页一个说 2 一个说 3,用户当场问哪个对
    // (2026-09-19 真机截图)。两页现在共用 `quotaValue` 这一条串,
    // 口径不一致就再也写不出来了。
    expect(find.text(l10n.quotaValue('2', 5)), findsOneWidget);
    expect(find.text('3 / 5'), findsNothing, reason: '已用口径不该再出现');
  });

  testWidgets('⭐ 额度条**递减**:满 → 空表示快用完了', (t) async {
    await _pump(t, _wrap(_free));
    // 剩余 2/5 → 条填 40%。画成已用的话是 60%,方向正好反过来:
    // 越用越满,读起来像进度在前进,而它表示的是"还剩多少"。
    final bar = t.widget<FractionallySizedBox>(
      find.byType(FractionallySizedBox).first,
    );
    expect(bar.widthFactor, closeTo(0.4, 0.001));
  });

  testWidgets('⭐ 已购未激活:绝不再出现购买按钮 —— 这是重复购买事故的根因', (t) async {
    await _pump(t, _wrap(_unactivated));
    final l10n = await _l10n();
    expect(find.text(l10n.paywallBuy), findsNothing);
    expect(find.text(l10n.paywallLoginToBuy), findsNothing);
    expect(find.text(l10n.benefitsStartNow('7')), findsOneWidget);
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

  // 真机实测(prod 数据造的):买了不激活满 30 天,权益页退回**未购态** ——
  // 付了 €7.99、票被作废,界面表现得像他从没买过。撞契约 I20:
  // 事前在售票上披露了「30 天失效」,事后什么都不说。
  testWidgets('买了没激活就作废:必须留下痕迹,不能退回未购态', (t) async {
    await _pump(t, _wrap(_expired, history: [_lapsedPass]));
    final l10n = await _l10n();
    expect(find.text(l10n.benefitsLapsedHead), findsOneWidget);
    expect(find.text(l10n.ticketVoid), findsOneWidget, reason: '那张作废的票要在');
    expect(find.text(l10n.paywallBuy), findsOneWidget, reason: '可以再买一张');
  });

  testWidgets('没激活过的票不许说「7 天已经用完」—— 他一天都没用过', (t) async {
    await _pump(t, _wrap(_expired, history: [_lapsedPass]));
    final l10n = await _l10n();
    expect(find.text(l10n.benefitsExpiredBody('7')), findsNothing);
    expect(find.text(l10n.benefitsEndedAt), findsNothing,
        reason: '这张票从来没有过到期日,存根位该写购买日');
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

  // ---- 多城市/多国(spec 2026-09-28 §3.3/§3.5)------------------------------

  testWidgets('⭐ 票名/卖点全部来自后端:荷兰的票不会写成巴黎', (t) async {
    await _pump(
        t,
        _wrap(const Entitlements(
          state: 'not_purchased',
          canPurchase: true,
          canRecognize: true,
          canAudioAny: false,
          offers: [_nl],
        )));
    final l10n = await _l10n();
    expect(find.text(l10n.paywallTitle('荷兰', '7')), findsOneWidget);
    expect(find.textContaining('巴黎'), findsNothing);
    expect(find.textContaining('国立博物馆'), findsOneWidget);
  });

  testWidgets('⭐ 不知道在哪家馆:每张可买的票各一个购买按钮,不猜「第一张」', (t) async {
    await _pump(
        t,
        _wrap(const Entitlements(
          state: 'not_purchased',
          canPurchase: true,
          canRecognize: true,
          canAudioAny: false,
          offers: [_paris, _nl],
        )));
    final l10n = await _l10n();
    expect(find.text(l10n.paywallBuy), findsNWidgets(2));
  });

  testWidgets('⭐ 从馆内来(?pass=):只卖这家馆的那张', (t) async {
    await _pump(
        t,
        _wrap(
            const Entitlements(
              state: 'not_purchased',
              canPurchase: true,
              canRecognize: true,
              canAudioAny: false,
              offers: [_paris, _nl],
            ),
            passId: 'nl_pass_7d'));
    final l10n = await _l10n();
    expect(find.text(l10n.paywallBuy), findsOneWidget);
    expect(find.text(l10n.paywallTitle('荷兰', '7')), findsOneWidget);
    expect(find.text(l10n.paywallTitle('巴黎', '7')), findsNothing);
  });

  testWidgets('⭐ 持巴黎票、从荷兰的馆点进来:照样能买荷兰的票(不能只显示「生效中」)', (t) async {
    final ent = Entitlements(
      state: 'active',
      canPurchase: true,
      canRecognize: true,
      canAudioAny: true,
      expiresAt: DateTime.now().add(const Duration(days: 4)),
      offers: const [_paris, _nl],
      passes: const [
        OwnedPass(
            productId: 'paris_pass_7d', label: '巴黎', days: 7, state: 'active'),
      ],
    );
    await _pump(t, _wrap(ent, passId: 'nl_pass_7d'));
    final l10n = await _l10n();
    expect(find.text(l10n.paywallBuy), findsOneWidget);
    expect(find.text(l10n.paywallTitle('荷兰', '7')), findsOneWidget);
  });

  testWidgets('已握在手里的票不再卖 —— 生效中再买同一张只会付两次钱', (t) async {
    await _pump(t, _wrap(_active, passId: 'paris_pass_7d'));
    final l10n = await _l10n();
    expect(find.text(l10n.paywallBuy), findsNothing);
  });

  testWidgets('这家馆暂未开售:说清楚,绝不回落卖巴黎票', (t) async {
    await _pump(t, _wrap(_free, passId: 'nl_pass_7d'));
    final l10n = await _l10n();
    expect(find.text(l10n.passNotOnSale), findsOneWidget);
    expect(find.text(l10n.paywallBuy), findsNothing);
  });

  testWidgets('⭐ 两张未激活票:权益页不放「开始」—— 猜错就烧掉另一国的 7 天', (t) async {
    final ent = Entitlements(
      state: 'purchased_not_activated',
      canPurchase: true,
      canRecognize: true,
      canAudioAny: false,
      activateBy: DateTime(2026, 10, 3),
      offers: const [_paris, _nl],
      passes: const [
        OwnedPass(
            productId: 'paris_pass_7d',
            label: '巴黎',
            days: 7,
            state: 'purchased_not_activated'),
        OwnedPass(
            productId: 'nl_pass_7d',
            label: '荷兰',
            days: 7,
            state: 'purchased_not_activated'),
      ],
    );
    await _pump(t, _wrap(ent));
    final l10n = await _l10n();
    expect(find.text(l10n.benefitsStartNow('7')), findsNothing);
    // 两张都列出来,用户看得出手里有哪几张
    expect(find.textContaining('荷兰'), findsWidgets);
    expect(find.textContaining('巴黎'), findsWidgets);
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
        l10n.benefitsNotStartedBody('7'),
        l10n.benefitsStartNow('7'),
        l10n.benefitsStartNowNote,
        l10n.benefitsExpiredBody('7'),
        l10n.paywallTitle('X', '7'),
        l10n.paywallPitch('A, B'),
        l10n.paywallPitchGeneric,
        l10n.passNotOnSale,
        l10n.benefitsPrevPass(d, d),
        l10n.benefitsEndedAt,
        l10n.ticketPaid,
        l10n.benefitsDateOnly(d),
        l10n.edgeUnknownHead,
        l10n.edgeUnknownBody,
        l10n.edgeUnknownNote,
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
