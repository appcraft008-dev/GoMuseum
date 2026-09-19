/// 全屏图片查看器：黑底、双指缩放/拖拽、左右翻页、credit 署名角标。
///
/// 消费端点4 `images[]`（R2 1600px 大图 + credit）。与详情头图轮播共享同一数据。
///
/// 关闭有两条路：**未放大时点击任意处**，以及左上角 ✕（放大状态下的唯一出口，
/// 别删）。为什么点击关闭要看缩放状态，见 `_ZoomablePageState._isZoomed`。
library;

import 'package:flutter/material.dart';
import 'package:gomuseum_app/core/network/image_request.dart';
import 'package:gomuseum_app/features/content/data/models/object_content_model.dart';
import 'package:gomuseum_app/theme/gm_tokens.dart';
import 'package:gomuseum_app/ui/gm/gm_icon.dart';

/// 拉起全屏画廊。[images] 非空；[initialIndex] 为进入时定位的图。
Future<void> showImageGallery(
  BuildContext context, {
  required List<ObjectImage> images,
  int initialIndex = 0,
}) {
  return Navigator.of(context).push(
    PageRouteBuilder<void>(
      opaque: false,
      barrierColor: Colors.black,
      pageBuilder: (_, __, ___) =>
          _ImageGallery(images: images, initialIndex: initialIndex),
    ),
  );
}

class _ImageGallery extends StatefulWidget {
  const _ImageGallery({required this.images, required this.initialIndex});
  final List<ObjectImage> images;
  final int initialIndex;

  @override
  State<_ImageGallery> createState() => _ImageGalleryState();
}

class _ImageGalleryState extends State<_ImageGallery> {
  late final PageController _pc;
  late int _i;

  @override
  void initState() {
    super.initState();
    _i = widget.initialIndex.clamp(0, widget.images.length - 1);
    _pc = PageController(initialPage: _i);
  }

  @override
  void dispose() {
    _pc.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final images = widget.images;
    final credit = images[_i].credit;
    final multi = images.length > 1;

    return Scaffold(
      backgroundColor: Colors.black,
      body: Stack(
        children: [
          // ponytail: InteractiveViewer 套在 PageView 里，scale=1 时不吃横拖 →
          // PageView 翻页；放大后 InteractiveViewer 吃拖动 → 平移。够用；要更顺
          // 需引 photo_view 依赖，非必要不加。
          PageView.builder(
            controller: _pc,
            itemCount: images.length,
            onPageChanged: (i) => setState(() => _i = i),
            itemBuilder: (_, i) => _ZoomablePage(
              onTapAtRest: () => Navigator.of(context).maybePop(),
              child: Center(
                child: Image.network(
                  // R2 直链原样透传；Wikimedia 兜底则取 1600px 档。
                  sizedImageUrl(images[i].url, 1600),
                  headers: kImageRequestHeaders,
                  fit: BoxFit.contain,
                  loadingBuilder: (_, child, progress) => progress == null
                      ? child
                      : const Center(
                          child: CircularProgressIndicator(
                              color: Colors.white24, strokeWidth: 2)),
                  errorBuilder: (_, __, ___) => const Center(
                      child: Icon(Icons.broken_image_outlined,
                          color: Colors.white30, size: 44)),
                ),
              ),
            ),
          ),

          // 关闭（放大状态下点击不响应，这里是唯一出口）
          SafeArea(
            child: Padding(
              padding: const EdgeInsets.all(8),
              child: GestureDetector(
                onTap: () => Navigator.of(context).maybePop(),
                behavior: HitTestBehavior.opaque,
                child: Container(
                  width: 38,
                  height: 38,
                  decoration: const BoxDecoration(
                      color: Colors.black38, shape: BoxShape.circle),
                  child: const GmIcon(GmIcons.close,
                      size: 20, color: Colors.white),
                ),
              ),
            ),
          ),

          // 页码 i/n
          if (multi)
            SafeArea(
              child: Align(
                alignment: Alignment.topCenter,
                child: Padding(
                  padding: const EdgeInsets.only(top: 12),
                  child: Container(
                    padding:
                        const EdgeInsets.symmetric(horizontal: 12, vertical: 5),
                    decoration: BoxDecoration(
                        color: Colors.black38,
                        borderRadius: BorderRadius.circular(999)),
                    child: Text('${_i + 1}/${images.length}',
                        style: GmText.sans(
                            size: 12, color: Colors.white, letterSpacing: 1)),
                  ),
                ),
              ),
            ),

          // credit 署名（合规项；null 不显示）
          if (credit != null && credit.trim().isNotEmpty)
            Positioned(
              left: 16,
              right: 16,
              bottom: 0,
              child: SafeArea(
                child: Padding(
                  padding: const EdgeInsets.symmetric(vertical: 12),
                  child: Text(
                    credit,
                    textAlign: TextAlign.center,
                    maxLines: 2,
                    overflow: TextOverflow.ellipsis,
                    style: GmText.sans(size: 10, color: Colors.white54),
                  ),
                ),
              ),
            ),
        ],
      ),
    );
  }
}

/// 一页可缩放的图。
///
/// 每页各自持一个 `TransformationController` —— 多图时缩放状态本就该互相独立，
/// 它同时也是"这页现在放大了没有"的唯一真相源。
class _ZoomablePage extends StatefulWidget {
  const _ZoomablePage({required this.child, required this.onTapAtRest});

  final Widget child;

  /// **只在未放大时**回调。放大状态下的点击一律吞掉，理由见 `_isZoomed`。
  final VoidCallback onTapAtRest;

  @override
  State<_ZoomablePage> createState() => _ZoomablePageState();
}

class _ZoomablePageState extends State<_ZoomablePage> {
  final _tc = TransformationController();

  @override
  void dispose() {
    _tc.dispose();
    super.dispose();
  }

  /// 点击关闭为什么要看缩放状态。
  ///
  /// 不是怕和双指捏放打架 —— 两指手势根本不会被判成 tap（tap 要求单指且几乎
  /// 无位移），那条没有风险。真正会咬人的是**放大之后**：用户拖动画面去看细节，
  /// 位移不到触摸阈值（约 18px）的那一下会被判成一次 tap，于是全屏退出、
  /// 刚定位好的画面全丢。用这道闸把它掐死：放大时点击什么都不做，用 ✕ 退出。
  /// iOS 相册、Instagram 都是这个规则。
  ///
  /// 容差取 1.01：捏回最小档时 `minScale` 的钳位结果未必正好是 1.0。
  bool get _isZoomed => _tc.value.getMaxScaleOnAxis() > 1.01;

  @override
  Widget build(BuildContext context) {
    return InteractiveViewer(
      transformationController: _tc,
      maxScale: 4,
      minScale: 1,
      // `behavior: opaque` 是必需的：没有它，图片两侧的黑边点不着，
      // 而全屏时上下（或左右）多半就是黑边 —— 有测试钉着。
      //
      // 至于 GestureDetector 在 InteractiveViewer 里还是外：**两种都能用**，
      // 实测过（本以为放外面会被 scale 识别器吃掉 tap，是想当然，不成立）。
      // 放里面是因为放大后的拖动交给父级 InteractiveViewer 处理即可，
      // 不必再进竞技场跟它抢；别因为"必须如此"而不敢动它。
      child: GestureDetector(
        behavior: HitTestBehavior.opaque,
        onTap: () {
          if (!_isZoomed) widget.onTapAtRest();
        },
        child: widget.child,
      ),
    );
  }
}
