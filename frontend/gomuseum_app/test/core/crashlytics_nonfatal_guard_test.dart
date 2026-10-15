// 10-14 V61 真机:字体下载断线(google_fonts 异步抛错)走 PlatformDispatcher.onError,
// 被记成致命崩溃,拉低无崩溃率。异步 Dart 错误不会让 App 退出,应按非致命上报。
import 'dart:io';

import 'package:flutter_test/flutter_test.dart';

void main() {
  test('异步未捕获错误按非致命上报', () {
    final src = File('lib/main.dart').readAsStringSync();
    final start = src.indexOf('PlatformDispatcher.instance.onError');
    expect(start, isNot(-1));
    final handler = src.substring(start, src.indexOf('};', start));
    expect(handler, contains('fatal: false'));
    expect(handler, isNot(contains('fatal: true')));
  });
}
