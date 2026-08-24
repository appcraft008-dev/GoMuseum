// 取景框双指变焦的倍率计算。钳制错了 setZoomLevel 会抛 CameraException，
// 部分机型还会黑屏，所以这段逻辑单独抽出来测。
import 'package:flutter_test/flutter_test.dart';
import 'package:gomuseum_app/features/recognition/presentation/pages/camera_page.dart';

void main() {
  group('computeZoomLevel', () {
    test('从 1× 捏合放大 2 倍 → 2×', () {
      expect(computeZoomLevel(startZoom: 1.0, scale: 2.0, min: 1.0, max: 8.0),
          2.0);
    });

    test('超过设备上限被钳制（否则 setZoomLevel 会抛）', () {
      expect(computeZoomLevel(startZoom: 4.0, scale: 4.0, min: 1.0, max: 8.0),
          8.0);
    });

    test('低于设备下限被钳制', () {
      expect(computeZoomLevel(startZoom: 1.0, scale: 0.1, min: 1.0, max: 8.0),
          1.0);
    });

    test('广角机 min 可以小于 1，此时允许缩到 0.5×', () {
      expect(computeZoomLevel(startZoom: 1.0, scale: 0.1, min: 0.5, max: 8.0),
          0.5);
    });

    test('连续手势从上一次的倍率继续，而不是每次从 1× 重算', () {
      // 第一次手势放大到 3×，松手；第二次手势 scale=1.5 应得 4.5× 而不是 1.5×。
      final first =
          computeZoomLevel(startZoom: 1.0, scale: 3.0, min: 1.0, max: 8.0);
      expect(first, 3.0);
      expect(computeZoomLevel(startZoom: first, scale: 1.5, min: 1.0, max: 8.0),
          4.5);
    });

    test('不支持变焦的机型（min==max==1）恒为 1×，手势自然失效', () {
      expect(computeZoomLevel(startZoom: 1.0, scale: 5.0, min: 1.0, max: 1.0),
          1.0);
    });
  });
}
