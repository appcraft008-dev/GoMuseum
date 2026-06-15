/// 装裱画框图片：surface 底 + line 边框，内嵌图片再加一圈 1px 边框
///
/// 对应设计稿讲解页画框与博物馆卡片图区；也提供小尺寸缩略图变体。
library;

import 'package:flutter/material.dart';

import 'package:gomuseum_app/theme/gm_tokens.dart';

/// 占位底色（图片缺失/加载中）
const Color _placeholder = Color(0xFFD8D2C2);

/// 带「装裱」外框的图片区
class GmFramedImage extends StatelessWidget {
  const GmFramedImage({
    super.key,
    required this.image,
    required this.height,
    this.framePadding = const EdgeInsets.all(10),
  });

  /// 任意 ImageProvider；null 时显示占位底色
  final ImageProvider? image;
  final double height;
  final EdgeInsets framePadding;

  @override
  Widget build(BuildContext context) {
    return Container(
      decoration: BoxDecoration(
        color: GmColors.surface,
        border: Border.all(color: GmColors.line),
      ),
      padding: framePadding,
      child: GmInnerImage(image: image, height: height),
    );
  }
}

/// 仅带 1px 边框的图片（卡片内图区 / 候选缩略图）
class GmInnerImage extends StatelessWidget {
  const GmInnerImage({
    super.key,
    required this.image,
    this.height,
    this.width,
  });

  final ImageProvider? image;
  final double? height;
  final double? width;

  @override
  Widget build(BuildContext context) {
    return Container(
      height: height,
      width: width ?? double.infinity,
      decoration: BoxDecoration(
        color: _placeholder,
        border: Border.all(color: GmColors.line),
        image: image == null
            ? null
            : DecorationImage(image: image!, fit: BoxFit.cover),
      ),
    );
  }
}

/// 双描边小缩略图（足迹条目 / Top3 馆藏组）：surface 粗边 + line 细外边
class GmThumb extends StatelessWidget {
  const GmThumb({super.key, required this.image, this.size = 36});

  final ImageProvider? image;
  final double size;

  @override
  Widget build(BuildContext context) {
    return Container(
      width: size,
      height: size,
      decoration: BoxDecoration(
        color: _placeholder,
        border: Border.all(color: GmColors.surface, width: 2),
        boxShadow: const [
          BoxShadow(color: GmColors.line, spreadRadius: 1, blurRadius: 0),
        ],
        image: image == null
            ? null
            : DecorationImage(image: image!, fit: BoxFit.cover),
      ),
    );
  }
}
