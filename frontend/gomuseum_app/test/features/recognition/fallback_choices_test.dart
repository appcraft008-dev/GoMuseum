// 「没认出 / 都不是 / 失败」选择卡布局(10-10 用户定):拍说明牌是唯一主按钮,说明在它上面;
// 输入编号(左)与重拍作品(右)并排同级。真实用户 17 次没认出 11 次直接放弃、0 次拍说明牌。
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gomuseum_app/features/recognition/presentation/pages/camera_page.dart';
import 'package:gomuseum_app/l10n/app_localizations.dart';
import 'package:gomuseum_app/ui/gm/gm.dart';

Future<List<String>> _pump(WidgetTester t, {bool showHint = true}) async {
  final taps = <String>[];
  await t.pumpWidget(MaterialApp(
    locale: const Locale('en'),
    localizationsDelegates: AppLocalizations.localizationsDelegates,
    supportedLocales: AppLocalizations.supportedLocales,
    home: Scaffold(
      body: SizedBox(
        width: 360,
        child: FallbackChoices(
          showHint: showHint,
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

  testWidgets('说明文字在主按钮上方', (t) async {
    await _pump(t);
    final hint = t.getTopLeft(find.textContaining('Museum labels show'));
    expect(hint.dy, lessThan(t.getTopLeft(find.byType(GmTicketButton)).dy));
  });

  testWidgets('输入编号在左、重拍在右,并排同高', (t) async {
    final taps = await _pump(t);
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
    await _pump(t, showHint: false);
    expect(find.textContaining('Museum labels show'), findsNothing);
  });
}
