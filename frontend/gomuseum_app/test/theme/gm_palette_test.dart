// test/theme/gm_palette_test.dart
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gomuseum_app/theme/gm_palette.dart';

void main() {
  test('light/dark 调色板取自 handoff token', () {
    expect(GmPalette.light.bg, const Color(0xFFF3EDDF));
    expect(GmPalette.light.accent, const Color(0xFFA14E28));
    expect(GmPalette.dark.bg, const Color(0xFF201A12));
    expect(GmPalette.dark.accent, const Color(0xFFD08050));
    // ctaDash 为半透明（45%）
    expect(GmPalette.light.ctaDash.a, closeTo(0.45, 0.02));
  });
}
