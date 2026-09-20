/// 作废戳的**尺寸风险**。
///
/// 戳存在的唯一理由是"一眼读出这张票废了" —— 而这套暖纸配色减不出作废感
/// (见 `GmTicket.voidStamp` 的说明),全靠它比正文**大一个层次**。
///
/// 放大到 24px 之后,最长的德语 `ABGELAUFEN` 在窄屏上顶到了票面边界。
/// `FittedBox` 不会破版,它会**默默把这一种语言缩小**,而且缩到什么程度
/// 都不报错。所以这里盯的不是"各语言一样大"(320 宽的屏上德语做不到),
/// 而是那条真正的底线:**缩完仍要明显大过正文**。
library;

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gomuseum_app/features/payment/presentation/widgets/gm_ticket.dart';
import 'package:gomuseum_app/l10n/app_localizations.dart';

/// 票面正文是 13px。戳缩到 1.4 倍以下就不再是"另一个层次"了,
/// 而是变回两层同级的字在打架 —— 那正是 2026-09-04 真机上被指出的问题。
const _minStampSize = 13.0 * 1.4;

/// 当下最窄的主流安卓机(Galaxy S 系列一档)的逻辑宽度;权益页两侧各留 20。
///
/// ⚠️ 不要调到 320:那个宽度下 `GmTicket` 的**票头** Row 本身就会溢出 35px
/// (与作废戳无关,把戳整个去掉照样溢出)。那是另一个问题,别混进这条测试。
const _narrow = Size(360, 800);

Widget _wrap(Widget child, Locale locale) => MaterialApp(
      locale: locale,
      localizationsDelegates: AppLocalizations.localizationsDelegates,
      supportedLocales: AppLocalizations.supportedLocales,
      home: Scaffold(
        body: Padding(
          padding: const EdgeInsets.symmetric(horizontal: 20),
          child: child,
        ),
      ),
    );

void main() {
  testWidgets('十种语言的作废戳都仍明显大过正文(最窄屏)', (t) async {
    t.view.physicalSize = _narrow;
    t.view.devicePixelRatio = 1.0;
    addTearDown(t.view.reset);

    final tooSmall = <String, String>{};
    for (final locale in AppLocalizations.supportedLocales) {
      final l10n = await AppLocalizations.delegate.load(locale);
      await t.pumpWidget(_wrap(
        GmTicket(
          torn: 1,
          faded: true,
          voidStamp: l10n.ticketVoid,
          child: const SizedBox(height: 80),
        ),
        locale,
      ));
      await t.pumpAndSettle();

      // FittedBox 的可用宽度 ÷ 文字的自然宽度 = 它实际用的缩放比。
      // 按「包着戳文字的那个」定位:票头的有效期也用了 FittedBox,
      // byType 会同时命中两个。
      final box = t.renderObject<RenderBox>(find.ancestor(
        of: find.text(l10n.ticketVoid),
        matching: find.byType(FittedBox),
      ));
      final text = t.renderObject<RenderBox>(find.text(l10n.ticketVoid));
      // 基准字号从**组件自己**读,不在测试里抄一份 —— 抄了的话改组件
      // 字号这条测试察觉不到,等于白测。
      final base = t.widget<Text>(find.text(l10n.ticketVoid)).style!.fontSize!;
      final rendered =
          base * (box.size.width / text.size.width).clamp(0.0, 1.0);
      if (rendered < _minStampSize) {
        tooSmall['${locale.languageCode} ${l10n.ticketVoid}'] =
            rendered.toStringAsFixed(1);
      }
    }

    expect(tooSmall, isEmpty,
        reason: '这些语言的戳被 FittedBox 缩到了正文 1.4 倍以下,'
            '盖上去读不出"作废":$tooSmall');
  });

  testWidgets('没传 voidStamp 就不画 —— 否则上面那条恒过', (t) async {
    await t.pumpWidget(_wrap(
      const GmTicket(
        torn: 1,
        faded: true,
        voidStamp: '已结束',
        child: SizedBox(height: 80),
      ),
      const Locale('zh'),
    ));
    expect(find.text('已结束'), findsOneWidget);

    await t.pumpWidget(_wrap(
      const GmTicket(torn: 1, faded: true, child: SizedBox(height: 80)),
      const Locale('zh'),
    ));
    expect(find.text('已结束'), findsNothing);
  });
}
