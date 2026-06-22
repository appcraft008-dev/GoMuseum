// test/theme/gm_theme_x_test.dart
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
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
}
