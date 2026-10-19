// 取景框提示是浮在相机画面上的气泡，每行（\n 分隔）在 360dp 窄屏、
// 1.3 倍系统字号下都要一行放下，否则 4 行气泡会挡住半个取景框（V64 真机）。
// 宽度必须用真实字体量，默认测试字体把拉丁文放宽约 2 倍。
import 'dart:convert';
import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gomuseum_app/theme/gm_tokens.dart';

import 'real_fonts.dart';

// 360dp − 气泡外边距 24×2 − 内边距 16×2
const _budget = 360.0 - 48 - 32;

void main() {
  testWidgets('取景框提示每行在 1.3 倍字号下一行放下', (t) async {
    await loadRealFonts(t);
    final tooWide = <String>[];
    final arbs = Directory('lib/l10n')
        .listSync()
        .whereType<File>()
        .where((f) => f.path.endsWith('.arb'));
    for (final f in arbs) {
      final arb = jsonDecode(f.readAsStringSync()) as Map<String, dynamic>;
      final tag = f.path.split('app_').last.replaceAll('.arb', '').split('_');
      GmText.locale = Locale.fromSubtags(
        languageCode: tag[0],
        scriptCode: tag.length > 1 ? tag[1] : null,
      );
      for (final key in ['camViewfinderHint', 'recViewfinderLabelHint']) {
        for (final line in (arb[key] as String).split('\n')) {
          final tp = TextPainter(
            text: TextSpan(text: line, style: GmText.sans(size: 12.5)),
            textDirection: TextDirection.ltr,
            textScaler: const TextScaler.linear(1.3),
          )..layout();
          if (tp.width > _budget) {
            tooWide.add('${tag.join('_')} $key ${tp.width.round()}: $line');
          }
          tp.dispose();
        }
      }
    }
    GmText.locale = null;
    expect(tooWide, isEmpty);
  });
}
