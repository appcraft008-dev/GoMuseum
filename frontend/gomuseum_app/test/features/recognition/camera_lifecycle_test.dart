// 切走再回来相机要不要重建。曾经在生命周期回调开头写
// `if (_controller == null) return;`，把 resumed 一起吞掉——开过图库/授权弹窗
// 回来后取景器永远转圈、快门按不动。这一档只跟 state 有关，单独抽出来钉住。
import 'package:flutter/widgets.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gomuseum_app/features/recognition/presentation/pages/camera_page.dart';

void main() {
  group('shouldRestartCamera', () {
    test('回前台且相机已被释放 → 重建（回归点：图库选完图回来）', () {
      expect(
          shouldRestartCamera(AppLifecycleState.resumed, hasController: false),
          isTrue);
    });

    // 正负成对：只测上面一条的话，一个"永远重建"的实现照样全绿。
    test('回前台但相机还活着 → 不重建（否则多开一个占着相机锁）', () {
      expect(
          shouldRestartCamera(AppLifecycleState.resumed, hasController: true),
          isFalse);
    });

    test('切走时不重建', () {
      for (final s in const [
        AppLifecycleState.inactive,
        AppLifecycleState.paused,
        AppLifecycleState.hidden,
        AppLifecycleState.detached,
      ]) {
        expect(shouldRestartCamera(s, hasController: false), isFalse,
            reason: '$s 不该重建相机');
      }
    });
  });
}
