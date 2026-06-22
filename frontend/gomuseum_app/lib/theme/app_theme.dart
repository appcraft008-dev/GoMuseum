/// GoMuseum 主题配置 — 暖纸手册 Catalogue（Claude Design 定稿）
///
/// 设计稿只有浅色方案，深浅色统一使用暖纸主题。
library;

import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';

import 'package:gomuseum_app/theme/gm_palette.dart';
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

  /// 暗色方案采用 BD（暖纸手册暗色）token
  static ThemeData darkTheme() {
    final p = GmPalette.dark;
    final textTheme = GoogleFonts.notoSansScTextTheme().apply(
      bodyColor: p.ink,
      displayColor: p.ink,
    );
    return ThemeData(
      useMaterial3: true,
      brightness: Brightness.dark,
      scaffoldBackgroundColor: p.bg,
      colorScheme: ColorScheme.dark(
        primary: p.accent,
        onPrimary: p.ctaInk,
        secondary: p.accentDeep,
        onSecondary: p.ctaInk,
        surface: p.surface,
        onSurface: p.ink,
        outline: p.line,
        error: const Color(0xFFEF6B5E), // BD 调色板无 error token，用暗色调赤红
      ),
      textTheme: textTheme,
      dividerColor: p.line,
      appBarTheme: AppBarTheme(
        backgroundColor: p.bg,
        foregroundColor: p.ink,
        elevation: 0,
        centerTitle: true,
        titleTextStyle: GmText.serif(size: 17, weight: FontWeight.w700),
      ),
      snackBarTheme: SnackBarThemeData(
        backgroundColor: p.ink,
        contentTextStyle: GmText.sans(size: 13.5, color: p.surface),
      ),
      progressIndicatorTheme: ProgressIndicatorThemeData(color: p.accent),
      textSelectionTheme: TextSelectionThemeData(
        cursorColor: p.accent,
        selectionColor: p.accent.withValues(alpha: 0.25),
        selectionHandleColor: p.accent,
      ),
    );
  }
}
