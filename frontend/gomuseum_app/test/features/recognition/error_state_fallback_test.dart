/// 「识别失败」页也要给出口(真机 2026-10-06:糊图失败后只剩「重拍」,用户无路可走)。
/// 失败恰恰是最需要「拍说明牌 / 输入编号或名称」的时候,和「没认出来」共用一套选择卡。
/// 拍照页的相机插件在单测里起不来,这里守源码结构(同 live_match_source_guard_test)。
library;

import 'dart:io';

import 'package:flutter_test/flutter_test.dart';

void main() {
  test('失败页与没认出来页共用选择卡(含拍说明牌、输入编号/名称)', () {
    final src =
        File('lib/features/recognition/presentation/pages/camera_page.dart')
            .readAsStringSync();
    String body(String name) {
      final start = src.indexOf('List<Widget> $name(');
      expect(start, isNot(-1), reason: '$name 不存在');
      final end = src.indexOf('\n  }\n', start);
      return src.substring(start, end);
    }

    expect(body('_errorContent'), contains('_fallbackChoices('));
    expect(body('_unrecognizedContent'), contains('_fallbackChoices('));
    final choices = body('_fallbackChoices');
    expect(choices, contains('recShootLabelBtn'));
    expect(choices, contains('recTypeNumberOrName'));
  });
}
