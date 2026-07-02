// lib/theme/gm_theme_x.dart
import 'package:flutter/material.dart';
import 'package:gomuseum_app/theme/gm_palette.dart';

extension GmThemeX on BuildContext {
  /// 当前生效的暖纸调色板（按 Theme.brightness 选 light/dark）。
  GmPalette get gm => Theme.of(this).brightness == Brightness.dark
      ? GmPalette.dark
      : GmPalette.light;

  /// 当前 UI 是否中日韩语（决定排版字距）。
  bool get isCjk => Localizations.localeOf(this).languageCode == 'zh';

  /// 标题字距：中文用设计的大字距（如 4/7）；拉丁文（en/fr）大字距很难看，
  /// 按比例收窄到接近 0（全大写 GOMUSEUM 保留一点点）。
  double gmLetterSpacing(double cjk) =>
      isCjk ? cjk : (cjk * 0.18).clamp(0.0, 1.2);

  /// 正文行高：中文字密、需大行高(1.9)才透气；拉丁文 1.9 反而行间松散、
  /// 段落"散架"，收到 1.6（拉丁常规书籍值）。
  double get gmBodyHeight => isCjk ? 1.9 : 1.6;
}

/// 不随主题切换的硬编码值（handoff「特殊规则」章节）。
class GmFixed {
  GmFixed._();
  static const Color viewfinderBg = Color(0xFF0F0C09); // 取景器背景
  static const Color heroTitle = Color(0xFFF6F1E4); // Hero 标题（白）
  static const Color heroCredit = Color(0x61F6F1E4); // Hero 版权 38%
  /// Hero 渐变遮罩：transparent(36%) → rgba(0,0,0,0.68)
  static const List<Color> heroScrim = [Color(0x00000000), Color(0xAD000000)];
  static const List<double> heroScrimStops = [0.36, 1.0];
}
