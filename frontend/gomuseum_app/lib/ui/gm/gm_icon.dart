/// 暖纸手册线性图标集
///
/// 路径数据移植自设计稿 `gm-shared.jsx` 的 GM_ICON_PATHS（24×24 viewBox，
/// 1.6pt 圆头描边），用 flutter_svg 按需着色渲染。
library;

import 'package:flutter/widgets.dart';
import 'package:flutter_svg/flutter_svg.dart';

/// 图标名（与设计稿键名一致）
enum GmIcons {
  home,
  compass,
  pin,
  sliders,
  camera,
  search,
  play,
  pause,
  mic,
  star,
  chevR,
  back,
  clock,
  headphones,
  close,
  flash,
  check,
  arrowR,
  globe,
  download,
  bell,
  shield,
  doc,
  user,
  photo,
  heart,
  mail,
  ticket,
  volume,
  lock,
  filter,
  qr,
}

const Map<GmIcons, List<String>> _iconPaths = {
  GmIcons.home: ['M3.5 11.5 12 4.5l8.5 7', 'M5.8 9.8V20h12.4V9.8'],
  GmIcons.compass: [
    'M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18Z',
    'M14.8 9.2l-1.7 4-4 1.6 1.7-4z',
  ],
  GmIcons.pin: [
    'M12 21s-7-6.2-7-11a7 7 0 0 1 14 0c0 4.8-7 11-7 11Z',
    'M12 12.3a2.3 2.3 0 1 0 0-4.6 2.3 2.3 0 0 0 0 4.6Z',
  ],
  GmIcons.sliders: [
    'M4 7h16 M4 17h16 M4 12h16',
    'M14.5 7a1.8 1.8 0 1 0 0 .01 M8.5 12a1.8 1.8 0 1 0 0 .01 M16 17a1.8 1.8 0 1 0 0 .01',
  ],
  GmIcons.camera: [
    'M3.5 8.2a1.7 1.7 0 0 1 1.7-1.7h2.1L9 4h6l1.7 2.5h2.1a1.7 1.7 0 0 1 1.7 1.7v9.6a1.7 1.7 0 0 1-1.7 1.7H5.2a1.7 1.7 0 0 1-1.7-1.7Z',
    'M12 16.6a3.6 3.6 0 1 0 0-7.2 3.6 3.6 0 0 0 0 7.2Z',
  ],
  GmIcons.search: [
    'M11 18a7 7 0 1 0 0-14 7 7 0 0 0 0 14Z',
    'M16.2 16.2 21 21',
  ],
  GmIcons.play: ['M9.2 7.2v9.6l8-4.8z'],
  GmIcons.pause: ['M8.5 6.5v11 M15.5 6.5v11'],
  GmIcons.mic: [
    'M12 14.5a2.8 2.8 0 0 0 2.8-2.8V6.8a2.8 2.8 0 1 0-5.6 0v4.9A2.8 2.8 0 0 0 12 14.5Z',
    'M6.5 11.7a5.5 5.5 0 0 0 11 0 M12 17.2V20.5 M9.2 20.5h5.6',
  ],
  GmIcons.star: [
    'm12 4.6 2.2 4.6 5 .7-3.6 3.6.8 5-4.4-2.4-4.4 2.4.8-5L4.8 9.9l5-.7z',
  ],
  GmIcons.chevR: ['m9.5 6 6 6-6 6'],
  GmIcons.back: ['M15 5l-7 7 7 7'],
  GmIcons.clock: [
    'M12 20.5a8.5 8.5 0 1 0 0-17 8.5 8.5 0 0 0 0 17Z',
    'M12 7.5V12l3.2 1.9',
  ],
  GmIcons.headphones: [
    'M4.5 17v-4.5a7.5 7.5 0 0 1 15 0V17',
    'M4.5 14.5h2.3v5.5H5.6a1.1 1.1 0 0 1-1.1-1.1Z',
    'M19.5 14.5h-2.3v5.5h1.2a1.1 1.1 0 0 0 1.1-1.1Z',
  ],
  GmIcons.close: ['M6 6l12 12 M18 6 6 18'],
  GmIcons.flash: ['M13 3 5.5 13.5h5L9.5 21 17 10.5h-5z'],
  GmIcons.check: ['m5 12.8 4.3 4.3L19 7.5'],
  GmIcons.arrowR: ['M4.5 12h14 M13 6.5l5.5 5.5-5.5 5.5'],
  GmIcons.globe: [
    'M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18Z',
    'M3.5 12h17 M12 3.5c-5.6 5.4-5.6 11.6 0 17 5.6-5.4 5.6-11.6 0-17Z',
  ],
  GmIcons.download: [
    'M12 4v10 M7.5 10.5 12 15l4.5-4.5',
    'M4.5 16.5V19a1.5 1.5 0 0 0 1.5 1.5h12A1.5 1.5 0 0 0 19.5 19v-2.5',
  ],
  GmIcons.bell: [
    'M6 16.5V11a6 6 0 0 1 12 0v5.5l1.5 2H4.5Z',
    'M10 20.5a2.2 2.2 0 0 0 4 0',
  ],
  GmIcons.shield: ['M12 3.5 5 6v5.5c0 4.6 3 7.6 7 9 4-1.4 7-4.4 7-9V6Z'],
  GmIcons.doc: [
    'M7 3.5h7L18.5 8v12.5h-11Z',
    'M14 3.5V8h4.5 M9.5 12.5h5 M9.5 16h5',
  ],
  GmIcons.user: [
    'M12 11.5a3.8 3.8 0 1 0 0-7.6 3.8 3.8 0 0 0 0 7.6Z',
    'M5 20.2c.8-3.5 3.6-5.4 7-5.4s6.2 1.9 7 5.4',
  ],
  GmIcons.photo: [
    'M4 5.5h16v13H4Z',
    'm5.5 16 4.5-5 4 4.2 2-2.1 2.5 2.9 M15.3 9.3a1 1 0 1 0 0 .01',
  ],
  GmIcons.heart: [
    'M12 19.5C7 15.7 4.5 12.9 4.5 9.9 4.5 7.7 6.2 6 8.4 6c1.4 0 2.8.7 3.6 1.9C12.8 6.7 14.2 6 15.6 6c2.2 0 3.9 1.7 3.9 3.9 0 3-2.5 5.8-7.5 9.6Z',
  ],
  GmIcons.mail: ['M3.5 6.5h17v11h-17Z', 'm4.5 7.5 7.5 6 7.5-6'],
  GmIcons.ticket: [
    'M4 7.5h16V11a1.6 1.6 0 0 0 0 3.2v3.3H4v-3.3A1.6 1.6 0 0 0 4 11Z',
    'M14.5 7.5v10',
  ],
  GmIcons.volume: [
    'M5 9.5v5h3l4.5 3.8V5.7L8 9.5Z',
    'M16 9a4.3 4.3 0 0 1 0 6 M18.3 7a7.4 7.4 0 0 1 0 10',
  ],
  GmIcons.lock: ['M7 11h10v8.5H7Z', 'M9 11V8a3 3 0 0 1 6 0v3'],
  GmIcons.filter: ['M5 7h14 M8 12h8 M10.5 17h3'],
  GmIcons.qr: [
    'M4.5 4.5h5v5h-5Z M14.5 4.5h5v5h-5Z M4.5 14.5h5v5h-5Z',
    'M14.5 14.5h2v2h-2Z M17.5 17.5h2v2h-2Z',
  ],
};

/// 线性描边图标（对应设计稿 GMIcon）
class GmIcon extends StatelessWidget {
  const GmIcon(
    this.icon, {
    super.key,
    this.size = 22,
    required this.color,
    this.strokeWidth = 1.6,
    this.fill = false,
  });

  final GmIcons icon;
  final double size;
  final Color color;
  final double strokeWidth;

  /// 实心填充（如已标星的 star），描边降为 0.8
  final bool fill;

  String _hex(Color c) =>
      '#${(c.toARGB32() & 0xFFFFFF).toRadixString(16).padLeft(6, '0')}';

  @override
  Widget build(BuildContext context) {
    final hex = _hex(color);
    final opacity = (color.a).toStringAsFixed(3);
    final paths = _iconPaths[icon]!
        .map((d) => '<path d="$d" '
            'fill="${fill ? hex : 'none'}" '
            '${fill ? 'fill-opacity="$opacity" ' : ''}'
            'stroke="$hex" stroke-opacity="$opacity" '
            'stroke-width="${fill ? 0.8 : strokeWidth}" '
            'stroke-linecap="round" stroke-linejoin="round"/>')
        .join();
    return SvgPicture.string(
      '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24">$paths</svg>',
      width: size,
      height: size,
    );
  }
}
