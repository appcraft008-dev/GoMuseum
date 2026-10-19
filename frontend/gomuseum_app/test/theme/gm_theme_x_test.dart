// test/theme/gm_theme_x_test.dart
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gomuseum_app/l10n/app_localizations.dart';
import 'package:gomuseum_app/theme/gm_palette.dart';
import 'package:gomuseum_app/theme/gm_theme_x.dart';

void main() {
  testWidgets('context.gm 随 Theme.brightness 切换调色板', (tester) async {
    late GmPalette captured;
    await tester.pumpWidget(MaterialApp(
      theme: ThemeData(brightness: Brightness.dark),
      home: Builder(builder: (c) {
        captured = c.gm;
        return const SizedBox();
      }),
    ));
    expect(captured.isDark, isTrue);
    expect(captured.bg, GmPalette.dark.bg);
  });

  // 正文对齐(10-19 用户定):中日韩两端对齐;拉丁文无自动断字,窄屏两端对齐词距拉出大空洞 → 左对齐。
  final expected = {
    Locale('zh'): TextAlign.justify,
    Locale.fromSubtags(languageCode: 'zh', scriptCode: 'Hant'):
        TextAlign.justify,
    Locale('ja'): TextAlign.justify,
    Locale('ko'): TextAlign.justify,
    Locale('en'): TextAlign.start,
    Locale('fr'): TextAlign.start,
    Locale('de'): TextAlign.start,
    Locale('es'): TextAlign.start,
    Locale('it'): TextAlign.start,
    Locale('pl'): TextAlign.start,
  };
  for (final e in expected.entries) {
    testWidgets('${e.key} 正文 ${e.value}', (t) async {
      late TextAlign got;
      await t.pumpWidget(MaterialApp(
        locale: e.key,
        localizationsDelegates: AppLocalizations.localizationsDelegates,
        supportedLocales: AppLocalizations.supportedLocales,
        home: Builder(builder: (context) {
          got = context.gmBodyAlign;
          return const SizedBox();
        }),
      ));
      expect(got, e.value);
    });
  }
}
