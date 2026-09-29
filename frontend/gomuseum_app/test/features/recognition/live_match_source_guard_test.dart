/// 只有**快门现场拍照**的命中能当作"人在这家馆"(spec 2026-09-29 §一)。
///
/// 图库上传/最近照片可能是在家翻旧照、出发前拿网图试 —— 用户原话指出过这会让首页
/// 「附近」判错。拍照页的相机插件在单测里起不来,所以这里守的是**源码结构**:
/// `_recognizeImage(..., live: true)` 只允许出现一次,且紧跟在 `takePicture()` 之后。
import 'dart:io';

import 'package:flutter_test/flutter_test.dart';

void main() {
  test('只有快门那条路径带 live: true', () {
    final src =
        File('lib/features/recognition/presentation/pages/camera_page.dart')
            .readAsStringSync();
    final calls =
        RegExp(r'_recognizeImage\(([^)]*)\)').allMatches(src).toList();
    final live =
        calls.where((m) => m.group(1)!.contains('live: true')).toList();
    expect(live, hasLength(1), reason: '图库/最近照片的识别不能标成现场');
    final before = src.substring(0, live.single.start);
    final lastPicture = before.lastIndexOf('takePicture()');
    final lastRecognize = before.lastIndexOf('_recognizeImage(');
    expect(lastPicture, greaterThan(lastRecognize),
        reason: 'live: true 必须是紧跟在快门 takePicture() 之后的那一次');
  });
}
