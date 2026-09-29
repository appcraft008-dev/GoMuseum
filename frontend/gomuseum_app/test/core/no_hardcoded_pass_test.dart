/// 一次性去硬编码的看门狗(spec 2026-09-28-multi-city-expansion §3.5)。
///
/// 第一个推上 Play 正式轨道的包会被永久装在用户手机上。它里面只要还写死着
/// 「巴黎」「paris_pass_7d」「四馆名」,第二个国家上线那天,所有已装用户就买不到票
/// —— 而那时唯一的修法是发版、等用户升级。这里扫的是**代码行**(注释里讲历史可以)。
import 'dart:io';

import 'package:flutter_test/flutter_test.dart';

const _forbidden = [
  'paris_pass_7d', // 商品 ID 由后端下发(馆包/402 的 pass、/me.offers)
  'GOMUSEUM · PARIS', // 票面刻印来自后端的票
  'kParisPass7d',
];

/// 这些文件是生成的,其中的字串来自 arb(arb 本身另有测试守着)。
bool _generated(String path) =>
    path.contains('/l10n/app_localizations') || path.endsWith('.g.dart');

void main() {
  test('lib/ 的代码行里不再写死任何一张具体的票', () {
    final hits = <String>[];
    for (final f in Directory('lib').listSync(recursive: true)) {
      if (f is! File || !f.path.endsWith('.dart') || _generated(f.path)) {
        continue;
      }
      final lines = f.readAsLinesSync();
      for (var i = 0; i < lines.length; i++) {
        final code = lines[i].split('//').first; // 注释里讲历史可以
        for (final bad in _forbidden) {
          if (code.contains(bad)) hits.add('${f.path}:${i + 1}  $bad');
        }
      }
    }
    expect(hits, isEmpty, reason: '写死的票会让第二个国家上线时必须发版');
  });

  test('arb 里不再点名具体的馆或写死天数的票名', () {
    // 卖点/票名的馆名与天数由占位符填(后端下发);点名四馆的旧文案不许回来
    for (final f in Directory('lib/l10n').listSync()) {
      if (f is! File || !f.path.endsWith('.arb')) continue;
      final s = f.readAsStringSync();
      expect(s.contains('"benefitsMuseums"'), isFalse, reason: f.path);
      expect(RegExp(r'"paywallTitle": "[^"]*\{label\}').hasMatch(s), isTrue,
          reason: '${f.path}:票名必须带 {label}');
      expect(RegExp(r'"paywallPitch": "[^"]*\{museums\}').hasMatch(s), isTrue,
          reason: '${f.path}:卖点必须带 {museums}');
    }
  });
}
