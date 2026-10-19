// 韩文 UI 文案要按词断行：词内相邻的谚文/字母/数字之间必须有 U+2060，
// 否则 Flutter 会在音节之间断行（"미|술관에서"）。漏了就跑
// `python3 scripts/ko_keep_all.py`（见脚本说明）。
import 'dart:convert';
import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:gomuseum_app/core/utils/keep_all.dart';

import 'real_fonts.dart';

void main() {
  test('app_ko.arb 每条文案词内都有 WORD JOINER', () {
    final arb = jsonDecode(File('lib/l10n/app_ko.arb').readAsStringSync())
        as Map<String, dynamic>;
    final bad = [
      for (final e in arb.entries)
        if (!e.key.startsWith('@') &&
            e.value is String &&
            keepAll(e.value as String) != e.value)
          e.key,
    ];
    expect(bad, isEmpty, reason: '跑 python3 scripts/ko_keep_all.py');
  });

  test('运行时拼出的日期也按词连上（intl 的 "2026년 10월 25일"）', () {
    expect(keepAll('2026년 10월 25일'), '2026\u2060년 10\u2060월 25\u2060일');
    expect(keepAll('Oct 25, 2026'), 'Oct 25, 2026'); // 不含谚文原样返回
  });

  testWidgets('WORD JOINER 让韩文只在空格处断行、且不占宽度', (t) async {
    await loadRealFonts(t);
    const plain = '미술관에서 처음 사용할 때부터 시작됩니다';
    final joined = keepAll(plain);
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
