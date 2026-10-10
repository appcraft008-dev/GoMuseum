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
    // 选择卡本体在 FallbackChoices 组件里(10-10 抽出,布局另有 fallback_choices_test)
    final fb = src.indexOf('List<Widget> _fallbackChoices(');
    expect(
        src.substring(fb, src.indexOf('];', fb)), contains('FallbackChoices('));
    final card = src.substring(src.indexOf('class FallbackChoices '));
    expect(card, contains('recShootLabelBtn'));
    expect(card, contains('recTypeNumberOrName'));
  });

  // 真机 10-06:网络两分钟里连断 4 次,服务端早算好了结果却没送到。「重拍」=新照片从头算
  // (一分多钟);「重试」重发同一张 → 服务端缓存命中,秒出且不重复扣。
  test('失败页有「重试」,重发的是同一张照片', () {
    final src =
        File('lib/features/recognition/presentation/pages/camera_page.dart')
            .readAsStringSync();
    final err = src.substring(src.indexOf('List<Widget> _errorContent('));
    expect(
        err.substring(0, err.indexOf('\n  }\n')), contains('_retryLastShot'));
    final retry = src.substring(src.indexOf('void _retryLastShot('));
    expect(retry.substring(0, retry.indexOf('\n  }\n')),
        contains('_recognizeImage(shot, live: _lastShotLive)'));
  });
}
