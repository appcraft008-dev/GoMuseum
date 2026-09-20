/// 票头右侧的有效期。
///
/// 原先写死 `7 JOURS` —— 注释把它当成和 `GOMUSEUM · PARIS` 一样的「票面刻印,
/// 不翻译」。但这两半不是一回事:品牌加地名是刻印,有效期是**产品规格**,
/// 十种语言的用户都得读懂这张票管几天。
///
/// 两条底线:①每种语言都拿到自己的写法;②最窄屏上不撑破票头
/// (意大利语 `7 GIORNI` 比法语原文长,加进来时真的溢出了 5.3px)。
library;

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gomuseum_app/features/payment/presentation/widgets/gm_ticket.dart';
import 'package:gomuseum_app/l10n/app_localizations.dart';

/// 与 void_stamp_test 同一个口径:最窄的主流安卓机,权益页两侧各留 20。
const _narrow = Size(360, 800);

Widget _wrap(Locale locale) => MaterialApp(
      locale: locale,
      localizationsDelegates: AppLocalizations.localizationsDelegates,
      supportedLocales: AppLocalizations.supportedLocales,
      home: const Scaffold(
        body: Padding(
          padding: EdgeInsets.symmetric(horizontal: 20),
          child: GmTicket(child: SizedBox(height: 80)),
        ),
      ),
    );

void main() {
  testWidgets('十种语言各自的有效期写法,且都不撑破票头(最窄屏)', (t) async {
    t.view.physicalSize = _narrow;
    t.view.devicePixelRatio = 1.0;
    addTearDown(t.view.reset);

    for (final locale in AppLocalizations.supportedLocales) {
      final l10n = await AppLocalizations.delegate.load(locale);
      await t.pumpWidget(_wrap(locale));
      await t.pumpAndSettle();

      expect(find.text(l10n.ticketDurationDays('7')), findsOneWidget,
          reason: '$locale 的票头应显示本语言的有效期');
      expect(tester_exceptions(t), isEmpty, reason: '$locale 的票头在 360 宽上溢出了');
    }
  });

  testWidgets('有效期不再写死法语:中文票头上没有 7 JOURS', (t) async {
    await t.pumpWidget(_wrap(const Locale('zh')));
    await t.pumpAndSettle();
    expect(find.text('7 JOURS'), findsNothing);
    expect(find.text('7 天'), findsOneWidget);
    // 品牌刻印不翻译,仍在。
    expect(find.text('GOMUSEUM · PARIS'), findsOneWidget);
  });
}

/// 本轮 pump 里累积的渲染异常(溢出会走到这里)。取完即清,
/// 否则一种语言的溢出会污染后面所有语言的断言。
List<Object> tester_exceptions(WidgetTester t) {
  final out = <Object>[];
  while (true) {
    final e = t.takeException();
    if (e == null) break;
    out.add(e as Object);
  }
  return out;
}
