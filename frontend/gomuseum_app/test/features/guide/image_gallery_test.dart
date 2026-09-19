/// 全屏画廊的关闭手势。
///
/// 两条纪律，写错了都不会报错、只会在手里变难用：
/// 1. 未放大时点击任意处要能关（原本只有左上角 ✕ 一条出路）；
/// 2. **放大之后点击不能关** —— 放大后拖动画面看细节，位移不到触摸阈值的
///    那一下会被判成 tap，退出全屏会让刚定位好的画面全丢。
///
/// 这里用**真手势**验（真双指捏放，不是去改内部 controller）：捏放能不能
/// 真正改到 scale、tap 会不会被 InteractiveViewer 的识别器吃掉，都是这组
/// 测试要答的问题，戳内部状态就全绕过去了。
library;

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gomuseum_app/features/content/data/models/object_content_model.dart';
import 'package:gomuseum_app/features/guide/presentation/widgets/image_gallery.dart';
import 'package:gomuseum_app/ui/gm/gm_icon.dart';

const _images = [
  ObjectImage(url: 'https://cdn.example/a.jpg', credit: '© Example'),
];

/// 打开画廊，返回"它还开着吗"。
Future<bool Function()> _open(WidgetTester t,
    {List<ObjectImage> images = _images}) async {
  await t.pumpWidget(MaterialApp(
    home: Scaffold(
      body: Builder(
        builder: (context) => Center(
          child: ElevatedButton(
            onPressed: () => showImageGallery(context, images: images),
            child: const Text('打开'),
          ),
        ),
      ),
    ),
  ));
  await t.tap(find.text('打开'));
  await t.pumpAndSettle();
  // 测试环境没有网络，Image.network 必然失败；与本组用例无关。
  t.takeException();

  expect(find.byType(InteractiveViewer), findsOneWidget, reason: '画廊没打开');
  return () => find.byType(InteractiveViewer).evaluate().isNotEmpty;
}

/// 真的双指捏放。Flutter 没有内置的 pinch 助手，两个指针各自往外移。
Future<void> _pinchOut(WidgetTester t) async {
  final c = t.getCenter(find.byType(InteractiveViewer));
  final g1 = await t.startGesture(c - const Offset(20, 0));
  final g2 = await t.startGesture(c + const Offset(20, 0));
  for (var i = 0; i < 5; i++) {
    await g1.moveBy(const Offset(-20, 0));
    await g2.moveBy(const Offset(20, 0));
    await t.pump();
  }
  await g1.up();
  await g2.up();
  await t.pumpAndSettle();
}

double _scale(WidgetTester t) => t
    .widget<InteractiveViewer>(find.byType(InteractiveViewer))
    .transformationController!
    .value
    .getMaxScaleOnAxis();

void main() {
  testWidgets('未放大时点击图片就能关 —— 不必去够左上角的 ✕', (t) async {
    final isOpen = await _open(t);

    await t.tap(find.byType(InteractiveViewer));
    await t.pumpAndSettle();

    expect(isOpen(), isFalse, reason: '点击被 InteractiveViewer 的识别器吃掉了');
  });

  testWidgets('🔴 放大之后点击不关 —— 否则微小平移会被判成 tap，放大的画面白丢', (t) async {
    final isOpen = await _open(t);

    await _pinchOut(t);
    expect(_scale(t), greaterThan(1.01), reason: '捏放没生效，后面的断言就没意义了');

    await t.tap(find.byType(InteractiveViewer));
    await t.pumpAndSettle();

    expect(isOpen(), isTrue, reason: '放大状态下点击把全屏关掉了');
  });

  testWidgets('放大状态下 ✕ 仍然能关 —— 它是这时唯一的出口', (t) async {
    final isOpen = await _open(t);
    await _pinchOut(t);
    expect(_scale(t), greaterThan(1.01));

    await t.tap(
        find.byWidgetPredicate((w) => w is GmIcon && w.icon == GmIcons.close));
    await t.pumpAndSettle();

    expect(isOpen(), isFalse, reason: '放大后就再也出不去了');
  });

  testWidgets('捏回原大小后点击又能关（对照组：闸不能只会关不会开）', (t) async {
    // 少了这条，一个"放大过就永久禁用点击"的实现也能让上面两条全绿。
    final isOpen = await _open(t);
    await _pinchOut(t);

    // 捏回去：两指相向而行。**不能走到重合** —— 两指距离归零时
    // InteractiveViewer 会 assert `scale != 0.0`，测试直接炸在框架里。
    final c = t.getCenter(find.byType(InteractiveViewer));
    final g1 = await t.startGesture(c - const Offset(120, 0));
    final g2 = await t.startGesture(c + const Offset(120, 0));
    for (var i = 0; i < 5; i++) {
      await g1.moveBy(const Offset(20, 0));
      await g2.moveBy(const Offset(-20, 0));
      await t.pump();
    }
    await g1.up();
    await g2.up();
    await t.pumpAndSettle();
    expect(_scale(t), lessThan(1.01), reason: '没捏回最小档');

    await t.tap(find.byType(InteractiveViewer));
    await t.pumpAndSettle();

    expect(isOpen(), isFalse, reason: '缩回原大小后点击应重新生效');
  });

  testWidgets('点击图片两侧的黑边也能关 —— 不只是图片本身', (t) async {
    final isOpen = await _open(t);

    // 贴着左边缘点，那里通常是黑底而不是图。
    final box = t.getRect(find.byType(InteractiveViewer));
    await t.tapAt(Offset(box.left + 4, box.center.dy));
    await t.pumpAndSettle();

    expect(isOpen(), isFalse);
  });
}
