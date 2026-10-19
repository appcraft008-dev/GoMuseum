// 候选全屏比对的底栏(10-19 用户定):滑到最后一个候选才出现「都不是」,
// 免得比对完还要退回候选页再点;不做「滑过头自动跳」(误触即丢候选、退不回)。
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gomuseum_app/features/recognition/presentation/pages/camera_page.dart';
import 'package:gomuseum_app/l10n/app_localizations.dart';

Future<List<String>> _pump(WidgetTester t, {required bool isLast}) async {
  final taps = <String>[];
  await t.pumpWidget(MaterialApp(
    locale: const Locale('zh'),
    localizationsDelegates: AppLocalizations.localizationsDelegates,
    supportedLocales: AppLocalizations.supportedLocales,
    home: Scaffold(
      body: CandidateViewerFooter(
        title: 'Olympia',
        isLast: isLast,
        onPick: () => taps.add('pick'),
        onNone: () => taps.add('none'),
      ),
    ),
  ));
  return taps;
}

void main() {
  testWidgets('不是最后一个候选:不显示「都不是」', (t) async {
    await _pump(t, isLast: false);
    expect(find.byKey(const Key('viewerNone')), findsNothing);
  });

  testWidgets('最后一个候选:显示「都不是」,点它只触发 onNone', (t) async {
    final taps = await _pump(t, isLast: true);
    await t.tap(find.byKey(const Key('viewerNone')));
    expect(taps, ['none']);
  });
}
