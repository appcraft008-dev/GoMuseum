/// 全屏图片查看器：黑底、双指缩放/拖拽、左右翻页、credit 署名角标。
///
/// 消费端点4 `images[]`（R2 1600px 大图 + credit）。与详情头图轮播共享同一数据。
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
            itemBuilder: (_, i) => InteractiveViewer(
              maxScale: 4,
              minScale: 1,
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

          // 关闭
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
