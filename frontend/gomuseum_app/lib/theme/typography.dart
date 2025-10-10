/// GoMuseum 应用字体系统
///
/// 基于 Roboto 字体族，定义了完整的文字样式层级
library;

import 'package:flutter/material.dart';
import 'colors.dart';

/// 应用字体样式
class AppTypography {
  AppTypography._(); // 私有构造函数

  // ==================== 字体族 ====================

  static const String fontFamily = 'Roboto';

  // ==================== 亮色模式文字主题 ====================

  static TextTheme lightTextTheme = TextTheme(
    // 大标题 (页面标题)
    displayLarge: TextStyle(
      fontFamily: fontFamily,
      fontSize: 32.0,
      fontWeight: FontWeight.bold,
      height: 1.2,
      color: AppColors.textPrimaryLight,
      letterSpacing: -0.5,
    ),
    displayMedium: TextStyle(
      fontFamily: fontFamily,
      fontSize: 28.0,
      fontWeight: FontWeight.bold,
      height: 1.2,
      color: AppColors.textPrimaryLight,
    ),
    displaySmall: TextStyle(
      fontFamily: fontFamily,
      fontSize: 24.0,
      fontWeight: FontWeight.bold,
      height: 1.3,
      color: AppColors.textPrimaryLight,
    ),

    // 标题 (卡片标题、区块标题)
    headlineLarge: TextStyle(
      fontFamily: fontFamily,
      fontSize: 20.0,
      fontWeight: FontWeight.bold,
      height: 1.3,
      color: AppColors.textPrimaryLight,
    ),
    headlineMedium: TextStyle(
      fontFamily: fontFamily,
      fontSize: 18.0,
      fontWeight: FontWeight.w600,
      height: 1.4,
      color: AppColors.textPrimaryLight,
    ),
    headlineSmall: TextStyle(
      fontFamily: fontFamily,
      fontSize: 16.0,
      fontWeight: FontWeight.w600,
      height: 1.4,
      color: AppColors.textPrimaryLight,
    ),

    // 正文 (主要内容文字)
    bodyLarge: TextStyle(
      fontFamily: fontFamily,
      fontSize: 16.0,
      fontWeight: FontWeight.normal,
      height: 1.5,
      color: AppColors.textPrimaryLight,
    ),
    bodyMedium: TextStyle(
      fontFamily: fontFamily,
      fontSize: 14.0,
      fontWeight: FontWeight.normal,
      height: 1.5,
      color: AppColors.textPrimaryLight,
    ),
    bodySmall: TextStyle(
      fontFamily: fontFamily,
      fontSize: 12.0,
      fontWeight: FontWeight.normal,
      height: 1.5,
      color: AppColors.textSecondaryLight,
    ),

    // 标签 (按钮文字、标签)
    labelLarge: TextStyle(
      fontFamily: fontFamily,
      fontSize: 14.0,
      fontWeight: FontWeight.w600,
      height: 1.4,
      color: AppColors.textPrimaryLight,
      letterSpacing: 0.5,
    ),
    labelMedium: TextStyle(
      fontFamily: fontFamily,
      fontSize: 12.0,
      fontWeight: FontWeight.w600,
      height: 1.4,
      color: AppColors.textSecondaryLight,
      letterSpacing: 0.5,
    ),
    labelSmall: TextStyle(
      fontFamily: fontFamily,
      fontSize: 11.0,
      fontWeight: FontWeight.w500,
      height: 1.4,
      color: AppColors.textSecondaryLight,
      letterSpacing: 0.5,
    ),
  );

  // ==================== 暗色模式文字主题 ====================

  static TextTheme darkTextTheme = TextTheme(
    displayLarge: lightTextTheme.displayLarge!.copyWith(
      color: AppColors.textPrimaryDark,
    ),
    displayMedium: lightTextTheme.displayMedium!.copyWith(
      color: AppColors.textPrimaryDark,
    ),
    displaySmall: lightTextTheme.displaySmall!.copyWith(
      color: AppColors.textPrimaryDark,
    ),
    headlineLarge: lightTextTheme.headlineLarge!.copyWith(
      color: AppColors.textPrimaryDark,
    ),
    headlineMedium: lightTextTheme.headlineMedium!.copyWith(
      color: AppColors.textPrimaryDark,
    ),
    headlineSmall: lightTextTheme.headlineSmall!.copyWith(
      color: AppColors.textPrimaryDark,
    ),
    bodyLarge: lightTextTheme.bodyLarge!.copyWith(
      color: AppColors.textPrimaryDark,
    ),
    bodyMedium: lightTextTheme.bodyMedium!.copyWith(
      color: AppColors.textPrimaryDark,
    ),
    bodySmall: lightTextTheme.bodySmall!.copyWith(
      color: AppColors.textSecondaryDark,
    ),
    labelLarge: lightTextTheme.labelLarge!.copyWith(
      color: AppColors.textPrimaryDark,
    ),
    labelMedium: lightTextTheme.labelMedium!.copyWith(
      color: AppColors.textSecondaryDark,
    ),
    labelSmall: lightTextTheme.labelSmall!.copyWith(
      color: AppColors.textSecondaryDark,
    ),
  );

  // ==================== 特殊文字样式 ====================

  /// 艺术品标题样式
  static TextStyle artworkTitle = TextStyle(
    fontFamily: fontFamily,
    fontSize: 20.0,
    fontWeight: FontWeight.bold,
    height: 1.3,
    color: AppColors.textPrimaryLight,
  );

  /// 艺术家名称样式
  static TextStyle artistName = TextStyle(
    fontFamily: fontFamily,
    fontSize: 16.0,
    fontWeight: FontWeight.w500,
    height: 1.4,
    color: AppColors.textSecondaryLight,
    fontStyle: FontStyle.italic,
  );

  /// 按钮文字样式
  static TextStyle button = TextStyle(
    fontFamily: fontFamily,
    fontSize: 16.0,
    fontWeight: FontWeight.w600,
    height: 1.4,
    letterSpacing: 0.5,
  );

  /// 数字统计样式 (置信度、评分等)
  static TextStyle statNumber = TextStyle(
    fontFamily: fontFamily,
    fontSize: 24.0,
    fontWeight: FontWeight.bold,
    height: 1.2,
    color: AppColors.primary,
  );
}
