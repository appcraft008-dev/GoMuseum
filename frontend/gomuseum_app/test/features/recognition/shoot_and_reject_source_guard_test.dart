// 10-14 V60 真机两条反馈,拍照页相机插件在单测里起不来,守源码结构:
// ① 按快门先拍照,再弹撕票激活 —— 反过来撕完票镜头早已不对着作品;
// ② 候选里点选进讲解页也带识别照片 phash,讲解页才显示「不是这件?」。
import 'dart:io';

import 'package:flutter_test/flutter_test.dart';

final _src =
    File('lib/features/recognition/presentation/pages/camera_page.dart')
        .readAsStringSync();

String _body(String signature) {
  final start = _src.indexOf(signature);
  expect(start, isNot(-1), reason: '找不到 $signature');
  final next = _src.indexOf(
      RegExp(r'\n  (Future<|void |bool |String\? )'), start + signature.length);
  return _src.substring(start, next);
}

void main() {
  test('快门:先 takePicture 再判额度/撕票', () {
    final shoot = _body('Future<void> _shoot()');
    final picture = shoot.indexOf('takePicture()');
    final gate = shoot.indexOf('_passActivatedIfPurchased(');
    expect(picture, isNot(-1));
    expect(gate, isNot(-1));
    expect(picture, lessThan(gate), reason: '撕票提示必须在拍完照之后弹');
  });

  test('快门:拍完立刻定格这张照片,不撕票再恢复取景', () {
    // 10-14 V61 真机:撕票面板后面还是实时取景+提示语,看着像没拍
    final shoot = _body('Future<void> _shoot()');
    final picture = shoot.indexOf('takePicture()');
    final freeze = shoot.indexOf('_captured = shot');
    final gate = shoot.indexOf('_passActivatedIfPurchased(');
    expect(freeze, greaterThan(picture));
    expect(freeze, lessThan(gate), reason: '弹撕票前就要定格');
    expect(shoot.indexOf('_captured = null'), greaterThan(gate),
        reason: '没撕开要回到实时取景');
  });

  test('候选点选进讲解页也带 phash', () {
    final goGuide = _body('Future<void> _goGuide(');
    expect(goGuide, contains('_artworkPhash'),
        reason: '候选点选时 rejectPhash 用识别照片的 phash');
    expect(
        RegExp(r'rejectPhash:\s*rejectPhash\s*\?\?').hasMatch(goGuide), isTrue);
  });
}
