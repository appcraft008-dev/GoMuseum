/// GoMuseum 主题配置 — 暖纸手册 Catalogue（Claude Design 定稿）
///
/// 设计稿只有浅色方案，深浅色统一使用暖纸主题。
library;

import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';

import 'package:gomuseum_app/theme/gm_tokens.dart';

class AppTheme {
  AppTheme._();

  static ThemeData lightTheme() {
    final textTheme = GoogleFonts.notoSansScTextTheme().apply(
      bodyColor: GmColors.ink,
      displayColor: GmColors.ink,
    );
    return ThemeData(
      useMaterial3: true,
      brightness: Brightness.light,
      scaffoldBackgroundColor: GmColors.bg,
      colorScheme: const ColorScheme.light(
        primary: GmColors.accent,
        onPrimary: GmColors.ctaInk,
        secondary: GmColors.accentDeep,
        onSecondary: GmColors.ctaInk,
        surface: GmColors.surface,
        onSurface: GmColors.ink,
        outline: GmColors.line,
        error: GmColors.error,
      ),
      textTheme: textTheme,
      dividerColor: GmColors.line,
      appBarTheme: AppBarTheme(
        backgroundColor: GmColors.bg,
        foregroundColor: GmColors.ink,
        elevation: 0,
        centerTitle: true,
        titleTextStyle: GmText.serif(size: 17, weight: FontWeight.w700),
      ),
      snackBarTheme: SnackBarThemeData(
        backgroundColor: GmColors.ink,
        contentTextStyle: GmText.sans(size: 13.5, color: GmColors.surface),
      ),
      progressIndicatorTheme:
          const ProgressIndicatorThemeData(color: GmColors.accent),
      textSelectionTheme: TextSelectionThemeData(
        cursorColor: GmColors.accent,
        selectionColor: GmColors.accent.withValues(alpha: 0.25),
        selectionHandleColor: GmColors.accent,
      ),
    );
  }

  /// 设计稿无暗色方案，暗色沿用暖纸主题保证视觉一致
  static ThemeData darkTheme() => lightTheme();
}
