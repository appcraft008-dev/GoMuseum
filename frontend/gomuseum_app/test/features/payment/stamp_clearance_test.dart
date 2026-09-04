/// 作废戳**压住了底下的字**。
///
/// 2026-09-04 真机:戳放大到 24px 之后,票面正文「不限次拍照识别,卢浮宫、
/// 奥赛…」里的「卢浮宫」被戳的笔画糊住了。压淡到 45% 并不解决这件事 ——
/// 中文笔画密,两组笔画叠在一起是**两边一起变糊**,不是一边透出来。
///
/// 上一轮我是拿浏览器重画的对比图判断"淡了就不挡"的,而图里恰恰没盯这个位置。
/// 眼睛看图不算验证,所以这条规矩交给测试:
///
///   ① 作废票不写卖点描述 —— 戳底下根本不该有字(这次的解法);
///   ② 戳不许掉到存根的日期上 —— 删掉正文后票会变矮,戳的落点跟着下移,
///      稍不注意就是"换了个字去压"。
library;

import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gomuseum_app/features/payment/data/entitlements.dart';
import 'package:gomuseum_app/features/payment/data/pass_history.dart';
import 'package:gomuseum_app/features/payment/domain/entities/user_benefits.dart';
import 'package:gomuseum_app/features/payment/presentation/pages/benefits_page.dart';
import 'package:gomuseum_app/features/payment/presentation/providers/benefits_provider.dart';
import 'package:gomuseum_app/features/payment/presentation/widgets/benefits_sections.dart';
import 'package:gomuseum_app/features/payment/presentation/widgets/gm_ticket.dart';
import 'package:gomuseum_app/l10n/app_localizations.dart';

const _narrow = Size(360, 800);

Widget _wrap(Widget child) => MaterialApp(
      locale: const Locale('zh'),
      localizationsDelegates: AppLocalizations.localizationsDelegates,
      supportedLocales: AppLocalizations.supportedLocales,
      home: Scaffold(
        body: Padding(
          padding: const EdgeInsets.symmetric(horizontal: 20),
          child: Center(child: child),
        ),
      ),
    );

const _expired = Entitlements(
  state: 'expired',
  canPurchase: true,
  canRecognize: true,
  canAudioAny: false,
  freeRecognitionsLeft: 0,
  freeRecognitionsTotal: 5,
);

/// [kind] = `expired-used`(7 天用完)或 `expired-lapsed`(买了没激活作废)。
/// 两条路各画一张作废票,都得验 —— 只验一条,另一条把 pitch 加回去照样绿。
Future<AppLocalizations> _pumpBenefits(WidgetTester t, String kind) async {
  final bought = DateTime.utc(2026, 8, 27, 1, 7);
  final rows = [
    kind == 'expired-used'
        ? PassRecord(
            productId: 'paris_pass_7d',
            state: 'expired',
            purchasedAt: bought,
            activatedAt: bought,
            expiresAt: DateTime.utc(2026, 9, 3, 1, 7),
          )
        : PassRecord(
            productId: 'paris_pass_7d',
            state: 'expired',
            purchasedAt: bought,
            expiresAt: DateTime.utc(2026, 9, 26, 1, 7),
          ),
  ];

  final container = ProviderContainer(overrides: [
    entitlementsProvider.overrideWith((ref) async => _expired),
    passHistoryProvider.overrideWith((ref) async => rows),
    benefitsStateProvider.overrideWith(() => _StubBenefits()),
  ]);
  addTearDown(container.dispose);

  await t.pumpWidget(UncontrolledProviderScope(
    container: container,
    child: const MaterialApp(
      localizationsDelegates: AppLocalizations.localizationsDelegates,
      supportedLocales: AppLocalizations.supportedLocales,
      locale: Locale('zh'),
      home: BenefitsPage(),
    ),
  ));
  await t.pumpAndSettle();
  return AppLocalizations.delegate.load(const Locale('zh'));
}

class _StubBenefits extends BenefitsState {
  @override
  FutureOr<UserBenefits> build() => UserBenefits.none();
}

/// 一张作废票:标题 + 已付 + 存根日期,没有卖点描述。
Widget _voidedTicket(String stamp, String date) => GmTicket(
      torn: 1,
      faded: true,
      voidStamp: stamp,
      stub: BenStubDate(label: '结束于', value: date, muted: true),
      child: const GmTicketFace(title: '巴黎 7 日通票', paidLabel: '已付'),
    );

void main() {
  // ⚠️ 这两条必须渲染**真的权益页**。第一版我拿测试里自己搭的假票来断言,
  // 结果把 benefits_page 的 pitch 原样加回去测试照样绿 —— 它只证明了
  // "我没传 pitch 时票上就没有 pitch",是句废话。
  for (final c in const [
    ('7 天用完', 'expired-used'),
    ('买了没激活作废', 'expired-lapsed'),
  ]) {
    testWidgets('作废票上没有卖点描述可挡 · ${c.$1}', (t) async {
      t.view.physicalSize = _narrow;
      t.view.devicePixelRatio = 1.0;
      addTearDown(t.view.reset);

      final l10n = await _pumpBenefits(t, c.$2);

      // 这句话本来在同一屏里出现两次:作废票 + 下面「再来一张」的在售票,
      // 上面那次还正好被戳压住。现在只该剩在售的那一次。
      expect(find.text(l10n.paywallPitch), findsOneWidget,
          reason: '作废票又写回卖点描述了 —— 戳会重新压在上面');
    });
  }

  testWidgets('戳不压票上任何一个字', (t) async {
    t.view.physicalSize = _narrow;
    t.view.devicePixelRatio = 1.0;
    addTearDown(t.view.reset);

    const date = '2026年9月3日 01:07';
    final l10n = await AppLocalizations.delegate.load(const Locale('zh'));
    await t.pumpWidget(_wrap(_voidedTicket(l10n.ticketVoid, date)));
    await t.pumpAndSettle();

    // 笔画级的遮挡测不了,包围盒是能落到断言里的最接近的东西。
    // 戳是斜的,getRect 给的是变换后两个对角点围出的框 —— 对 -10° 够用。
    final stamp = t.getRect(find.text(l10n.ticketVoid));

    final hit = <String, Rect>{};
    for (final e in find.byType(Text).evaluate()) {
      final text = (e.widget as Text).data;
      if (text == null || text == l10n.ticketVoid) continue;
      final r = t.getRect(find.byWidget(e.widget));
      if (stamp.overlaps(r)) hit[text] = r;
    }

    expect(hit, isEmpty,
        reason: '戳 $stamp 压住了这些字:$hit\n'
            '票面正文删掉后戳的落点会移动 —— GmTicketFace 里 pitch 为空时'
            '那段留白正是在给戳留落脚处,调小它戳就会骑到票头或标题上。');
  });

  testWidgets('日期真的在票上 —— 否则上面那条恒过', (t) async {
    t.view.physicalSize = _narrow;
    t.view.devicePixelRatio = 1.0;
    addTearDown(t.view.reset);

    const date = '2026年9月3日 01:07';
    final l10n = await AppLocalizations.delegate.load(const Locale('zh'));
    await t.pumpWidget(_wrap(_voidedTicket(l10n.ticketVoid, date)));
    await t.pumpAndSettle();

    expect(find.text(date), findsOneWidget);
    expect(find.text(l10n.ticketVoid), findsOneWidget);
  });
}
