/// GoMuseum 暖纸手册设计令牌
///
/// 来源：Claude Design 定稿 `docs/design/claude-design-bundle/project/gm-shared.jsx`
/// 中的 GM_THEMES.B（暖纸手册 Catalogue：米纸底、赤陶点缀、目录编号）。
library;

import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';

/// 暖纸手册色彩令牌
class GmColors {
  GmColors._();

  /// 页面米纸底
  static const Color bg = Color(0xFFF3EDDF);

  /// 卡片 / 装裱底
  static const Color surface = Color(0xFFFBF7EC);

  /// 主文字（墨色）
  static const Color ink = Color(0xFF2C2316);

  /// 次级文字
  static const Color sub = Color(0xFF8A7A5F);

  /// 弱化文字 / 未激活
  static const Color faint = Color(0xFFB0A283);

  /// 发丝线 / 边框
  static const Color line = Color(0xFFDCD2B8);

  /// 赤陶强调色
  static const Color accent = Color(0xFFA14E28);

  /// 强调深色（激活态）
  static const Color accentDeep = Color(0xFF7E3A1C);

  /// 门票式 CTA 底色
  static const Color ctaBg = accent;

  /// 门票式 CTA 文字色
  static const Color ctaInk = Color(0xFFFBF7EC);

  /// 问答 chip 底色
  static const Color chipBg = Color(0xFFEAE2CD);

  /// 识别页深色取景底
  static const Color scanBg = Color(0xFF171310);

  /// 识别页浅色前景
  static const Color scanInk = Color(0xFFF6F1E4);

  /// 错误色（沿用赤陶系的深红，保持暖调）
  static const Color error = Color(0xFF9B2C20);
}

/// 暖纸手册字体工具
///
/// 标题用衬线 Noto Serif SC，正文用 Noto Sans SC（设计稿 fallback
/// Songti SC / PingFang SC 由系统字体链自动兜底）。
class GmText {
  GmText._();

  /// CJK 回退字体族名（懒加载注册）。拉丁字形由主字体渲染，
  /// 中日韩字形自动回退到这些 …SC 字体——按字形选字体、无需判断语言。
  static final String _serifCjkFamily = GoogleFonts.notoSerifSc().fontFamily!;
  static final String _sansCjkFamily = GoogleFonts.notoSansSc().fontFamily!;

  /// 衬线标题样式
  ///
  /// 拉丁字母用 **Noto Serif**（优雅拉丁衬线），中文自动回退 **Noto Serif SC**，
  /// 解决「中英共用 SC 体导致拉丁字母不好看」。
  /// `color` 缺省 null —— 不烘焙固定色，随主题 `DefaultTextStyle`(ink) 切换明暗。
  static TextStyle serif({
    double size = 16,
    FontWeight weight = FontWeight.w400,
    Color? color,
    double? letterSpacing,
    double? height,
  }) {
    return GoogleFonts.notoSerif(
      fontSize: size,
      fontWeight: weight,
      color: color,
      letterSpacing: letterSpacing,
      height: height,
    ).copyWith(fontFamilyFallback: [_serifCjkFamily]);
  }

  /// 无衬线正文样式：拉丁用 **Noto Sans**，中文回退 **Noto Sans SC**。
  /// `color` 缺省 null —— 同 [serif]，随主题继承。
  static TextStyle sans({
    double size = 14,
    FontWeight weight = FontWeight.w400,
    Color? color,
    double? letterSpacing,
    double? height,
  }) {
    return GoogleFonts.notoSans(
      fontSize: size,
      fontWeight: weight,
      color: color,
      letterSpacing: letterSpacing,
      height: height,
    ).copyWith(fontFamilyFallback: [_sansCjkFamily]);
  }

  /// 小标签（GMEyebrow）：11px / 字距 2.2 / sub 色
  static TextStyle eyebrow({Color color = GmColors.sub}) {
    return sans(size: 11, letterSpacing: 2.2, color: color);
  }
}
