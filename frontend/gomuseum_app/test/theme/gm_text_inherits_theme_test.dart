// GmText 默认色应随主题继承（暗色不再烘焙亮色墨 → 修首页暗色文字看不清）。
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gomuseum_app/theme/app_theme.dart';
import 'package:gomuseum_app/theme/gm_palette.dart';
import 'package:gomuseum_app/theme/gm_tokens.dart';

Color _renderedColor(WidgetTester tester, String text) {
  final rich = tester.widget<RichText>(
    find.descendant(of: find.text(text), matching: find.byType(RichText)),
  );
  return (rich.text as TextSpan).style!.color!;
}

void main() {
  testWidgets('GmText.serif() 无显式色：暗色模式继承暗主题 ink（浅色），不再是近黑', (tester) async {
    await tester.pumpWidget(MaterialApp(
      theme: AppTheme.lightTheme(),
      darkTheme: AppTheme.darkTheme(),
      themeMode: ThemeMode.dark,
      home: Scaffold(
        body: Text('GOMUSEUM', style: GmText.serif(size: 13)),
      ),
    ));
    final c = _renderedColor(tester, 'GOMUSEUM');
    expect(c, GmPalette.dark.ink); // #EFE6D2 浅色，暗底可见
    expect(c, isNot(GmPalette.light.ink)); // 不是 #2C2316 近黑
  });

  testWidgets('GmText.sans() 无显式色：亮色模式仍为亮主题 ink（不回归）', (tester) async {
    await tester.pumpWidget(MaterialApp(
      theme: AppTheme.lightTheme(),
      darkTheme: AppTheme.darkTheme(),
      themeMode: ThemeMode.light,
      home: Scaffold(
        body: Text('正文', style: GmText.sans(size: 14)),
      ),
    ));
    expect(_renderedColor(tester, '正文'), GmPalette.light.ink);
  });
}
