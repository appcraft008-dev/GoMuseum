// 相机页方向:手机尺寸锁竖屏(横屏布局把取景框挤到上半截),大屏(平板/折叠屏内屏)不锁。
// 锁竖屏不影响横拍——相机插件按重力感应给照片定方向,后端再按 EXIF 转正。
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gomuseum_app/features/recognition/presentation/pages/camera_page.dart';

void main() {
  test('手机(最短边 <600dp)竖着进或横着进都锁竖屏', () {
    expect(cameraOrientations(const Size(412, 915)),
        [DeviceOrientation.portraitUp]);
    expect(cameraOrientations(const Size(915, 412)),
        [DeviceOrientation.portraitUp]);
  });

  test('平板/折叠屏内屏(最短边 ≥600dp)不锁', () {
    expect(cameraOrientations(const Size(1280, 800)), isEmpty);
    expect(cameraOrientations(const Size(673, 841)), isEmpty);
  });
}
