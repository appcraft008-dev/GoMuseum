// 「没认出 / 都不是 / 失败」选择卡布局(10-10 用户定):拍说明牌是唯一主按钮;
// 10-13 用户定:卡里不再放「小标牌上有作品名…」说明(和外层一行说明、按钮文字重复,太啰嗦);
// 输入编号(左)与重拍作品(右)并排同级。真实用户 17 次没认出 11 次直接放弃、0 次拍说明牌。
// 10-11:已拍过墙签时主按钮换成输入编号(墙签文字已预填),不再给拍说明牌(重拍同一张墙签结果一样);
// 次按钮文字放不下(大字号/德语)时缩小到一行,不换行。
// 10-19 用户改定:不缩字(德语曾缩到 0.57 倍),放不下换两行、两个按钮等高。
// 10-19 V64 真机:大字号下并排折成两行难看 → 任一个一行放不下就上下各占整行。
import 'package:flutter/material.dart';
import 'package:flutter/rendering.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gomuseum_app/features/recognition/presentation/pages/camera_page.dart';
import 'package:gomuseum_app/l10n/app_localizations.dart';
import 'package:gomuseum_app/ui/gm/gm.dart';

import '../../i18n/real_fonts.dart';

Future<List<String>> _pump(WidgetTester t,
    {bool labelSeen = false,
    Locale locale = const Locale('en'),
    double textScale = 1.0}) async {
  final taps = <String>[];
  await t.pumpWidget(MaterialApp(
    locale: locale,
    builder: (context, child) => MediaQuery(
      data: MediaQuery.of(context)
          .copyWith(textScaler: TextScaler.linear(textScale)),
      child: child!,
    ),
    localizationsDelegates: AppLocalizations.localizationsDelegates,
    supportedLocales: AppLocalizations.supportedLocales,
    home: Scaffold(
      body: SizedBox(
        width: 360,
        child: FallbackChoices(
          labelSeen: labelSeen,
          onShootLabel: () => taps.add('label'),
          onSearch: () => taps.add('search'),
          onRetake: () => taps.add('retake'),
        ),
      ),
    ),
  ));
  return taps;
}

void main() {
  testWidgets('拍说明牌是唯一主按钮', (t) async {
    final taps = await _pump(t);
    expect(find.byType(GmTicketButton), findsOneWidget);
    await t.tap(find.byType(GmTicketButton));
    expect(taps, ['label']);
  });

  testWidgets('卡里只有按钮,没有说明文字(10-13 嫌啰嗦)', (t) async {
    await _pump(t, locale: const Locale('zh'));
    expect(find.textContaining('小标牌'), findsNothing);
    expect(find.byType(Text), findsNWidgets(3)); // 三个按钮的文字
  });

  testWidgets('输入编号在左、重拍在右,并排同高', (t) async {
    final taps = await _pump(t);
    await loadRealFonts(t); // 方块字体会误判成放不下而改成上下排
    await t.pump();
    final search = find.byKey(const Key('fbSearch'));
    final retake = find.byKey(const Key('fbRetake'));
    expect(t.getTopLeft(search).dx, lessThan(t.getTopLeft(retake).dx));
    expect(t.getTopLeft(search).dy, t.getTopLeft(retake).dy);
    expect(t.getSize(search).height, t.getSize(retake).height);
    await t.tap(search);
    await t.tap(retake);
    expect(taps, ['search', 'retake']);
  });

  testWidgets('已读出墙签时不重复说明', (t) async {
    await _pump(t, labelSeen: true);
    expect(find.textContaining('Museum labels show'), findsNothing);
  });

  testWidgets('已拍过墙签:主按钮是输入编号,下面只剩整行的重拍', (t) async {
    final taps = await _pump(t, labelSeen: true);
    expect(find.byType(GmTicketButton), findsOneWidget);
    await t.tap(find.byType(GmTicketButton));
    final retake = find.byKey(const Key('fbRetake'));
    expect(find.byKey(const Key('fbSearch')), findsNothing);
    expect(find.byKey(const Key('fbShootLabel')), findsNothing);
    expect(t.getSize(retake).width, 360);
    await t.tap(retake);
    expect(taps, ['search', 'retake']);
  });

  for (final seen in [false, true]) {
    testWidgets('次按钮德语 + 1.5 倍字号:不缩字、不截断、等高(labelSeen=$seen)', (t) async {
      await _pump(t,
          labelSeen: seen, locale: const Locale('de'), textScale: 1.5);
      await loadRealFonts(t); // 方块测试字体把拉丁文宽度放大约 2 倍，换不换行判不准
      await t.pump();
      final keys = [if (!seen) 'fbSearch', 'fbRetake'];
      for (final key in keys) {
        final text = find.descendant(
            of: find.byKey(Key(key)), matching: find.byType(RichText));
        final p = t.renderObject<RenderParagraph>(text);
        expect(p.maxLines, 2, reason: key);
        expect(p.didExceedMaxLines, isFalse, reason: key);
        expect(find.ancestor(of: text, matching: find.byType(FittedBox)),
            findsNothing,
            reason: key);
      }
      expect(t.takeException(), isNull);
    });
  }

  testWidgets('英文 2 倍字号放不下:上下各占整行,每个一行', (t) async {
    await _pump(t, textScale: 2.0);
    await loadRealFonts(t);
    await t.pump();
    final search = find.byKey(const Key('fbSearch'));
    final retake = find.byKey(const Key('fbRetake'));
    expect(t.getSize(search).width, 360);
    expect(t.getSize(retake).width, 360);
    expect(t.getTopLeft(retake).dy, greaterThan(t.getTopLeft(search).dy));
    for (final b in [search, retake]) {
      final p = t.renderObject<RenderParagraph>(
          find.descendant(of: b, matching: find.byType(RichText)));
      expect(
          p
              .getBoxesForSelection(TextSelection(
                  baseOffset: 0, extentOffset: p.text.toPlainText().length))
              .map((r) => r.top)
              .toSet()
              .length,
          1);
    }
  });

  testWidgets('英文 1.5 倍字号:「No. or title」仍并排(10-19 用户定缩写)', (t) async {
    await _pump(t, textScale: 1.5);
    await loadRealFonts(t);
    await t.pump();
    expect(t.getTopLeft(find.byKey(const Key('fbSearch'))).dy,
        t.getTopLeft(find.byKey(const Key('fbRetake'))).dy);
  });
}
