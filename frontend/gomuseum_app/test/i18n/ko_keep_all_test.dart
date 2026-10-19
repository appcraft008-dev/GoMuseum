// 韩文 UI 文案要按词断行：词内相邻的谚文/字母/数字之间必须有 U+2060，
// 否则 Flutter 会在音节之间断行（"미|술관에서"）。漏了就跑
// `python3 scripts/ko_keep_all.py`（见脚本说明）。
import 'dart:convert';
import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'real_fonts.dart';

final _missing = RegExp(
    r'(?<=[\uAC00-\uD7A3])(?=[\uAC00-\uD7A30-9A-Za-z{])|(?<=[0-9A-Za-z}])(?=[\uAC00-\uD7A3])');

void main() {
  test('app_ko.arb 每条文案词内都有 WORD JOINER', () {
    final arb = jsonDecode(File('lib/l10n/app_ko.arb').readAsStringSync())
        as Map<String, dynamic>;
    final bad = [
      for (final e in arb.entries)
        if (!e.key.startsWith('@') &&
            e.value is String &&
            _missing.hasMatch(e.value as String))
          e.key,
    ];
    expect(bad, isEmpty, reason: '跑 python3 scripts/ko_keep_all.py');
  });

  testWidgets('WORD JOINER 让韩文只在空格处断行、且不占宽度', (t) async {
    await loadRealFonts(t);
    const plain = '미술관에서 처음 사용할 때부터 시작됩니다';
    final joined = plain.replaceAllMapped(
        RegExp(r'(?<=[\uAC00-\uD7A3])(?=[\uAC00-\uD7A3])'), (_) => '\u2060');
    TextPainter p(String s, [double? w]) => TextPainter(
        text: TextSpan(
            text: s,
            style: const TextStyle(
                fontFamily: 'NotoSansKR_regular', fontSize: 14)),
        textDirection: TextDirection.ltr)
      ..layout(maxWidth: w ?? double.infinity);

    expect(p(joined).width, closeTo(p(plain).width, 0.5));
    // 每个换行点前一个字符都应是空格（原文去掉 WJ 后按行切）
    final tp = p(joined, 120);
    for (final m in tp.computeLineMetrics().skip(1)) {
      final pos = tp.getPositionForOffset(Offset(0, m.baseline)).offset;
      expect(joined[pos - 1], ' ', reason: '在 $pos 处拦腰断行');
    }
  });
}
