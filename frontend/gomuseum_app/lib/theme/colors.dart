/// GoMuseum 应用色彩系统
///
/// 基于 Material Design 3.0 规范，定义了完整的色彩体系
/// 包含亮色模式和暗色模式的配色方案
library;

import 'package:flutter/material.dart';

/// 应用色彩常量
class AppColors {
  AppColors._(); // 私有构造函数，防止实例化

  // ==================== 主色系 ====================

  /// 主色 - 深蓝色 (博物馆专业性)
  static const Color primary = Color(0xFF1E3A8A);
  static const Color primaryLight = Color(0xFF3B82F6);
  static const Color primaryDark = Color(0xFF1E40AF);

  /// 辅色 - 金色 (艺术价值)
  static const Color secondary = Color(0xFFF59E0B);
  static const Color secondaryLight = Color(0xFFFBBF24);
  static const Color secondaryDark = Color(0xFFD97706);

  // ==================== 功能色 ====================

  /// 成功色
  static const Color success = Color(0xFF10B981);
  static const Color successLight = Color(0xFF34D399);
  static const Color successDark = Color(0xFF059669);

  /// 错误色
  static const Color error = Color(0xFFEF4444);
  static const Color errorLight = Color(0xFFF87171);
  static const Color errorDark = Color(0xFFDC2626);

  /// 警告色
  static const Color warning = Color(0xFFF59E0B);
  static const Color warningLight = Color(0xFFFBBF24);
  static const Color warningDark = Color(0xFFD97706);

  /// 信息色
  static const Color info = Color(0xFF3B82F6);
  static const Color infoLight = Color(0xFF60A5FA);
  static const Color infoDark = Color(0xFF2563EB);

  // ==================== 中性色 (亮色模式) ====================

  /// 背景色
  static const Color backgroundLight = Color(0xFFFFFFFF);
  static const Color surfaceLight = Color(0xFFF9FAFB);
  static const Color cardLight = Color(0xFFFFFFFF);

  /// 文字色
  static const Color textPrimaryLight = Color(0xFF1F2937);
  static const Color textSecondaryLight = Color(0xFF6B7280);
  static const Color textDisabledLight = Color(0xFF9CA3AF);

  /// 边框色
  static const Color borderLight = Color(0xFFE5E7EB);
  static const Color dividerLight = Color(0xFFF3F4F6);

  // ==================== 中性色 (暗色模式) ====================

  /// 背景色
  static const Color backgroundDark = Color(0xFF121212);
  static const Color surfaceDark = Color(0xFF1E1E1E);
  static const Color cardDark = Color(0xFF2C2C2C);

  /// 文字色
  static const Color textPrimaryDark = Color(0xFFF9FAFB);
  static const Color textSecondaryDark = Color(0xFFD1D5DB);
  static const Color textDisabledDark = Color(0xFF6B7280);

  /// 边框色
  static const Color borderDark = Color(0xFF374151);
  static const Color dividerDark = Color(0xFF1F2937);

  // ==================== 特殊色 ====================

  /// 阴影色
  static const Color shadowLight = Color(0x1A000000);
  static const Color shadowDark = Color(0x33000000);

  /// 遮罩色
  static const Color overlayLight = Color(0x4D000000);
  static const Color overlayDark = Color(0x66000000);

  /// 高亮色
  static const Color highlightLight = Color(0x0F1E3A8A);
  static const Color highlightDark = Color(0x1F3B82F6);

  // ==================== 渐变色 ====================

  /// 主要渐变 (用于 Hero 区域)
  static const LinearGradient primaryGradient = LinearGradient(
    begin: Alignment.topLeft,
    end: Alignment.bottomRight,
    colors: [primary, primaryLight],
  );

  /// 金色渐变 (用于特殊元素)
  static const LinearGradient accentGradient = LinearGradient(
    begin: Alignment.topLeft,
    end: Alignment.bottomRight,
    colors: [secondary, secondaryLight],
  );

  // ==================== 透明度变体 ====================

  /// 获取带透明度的主色
  static Color primaryWithOpacity(double opacity) =>
      primary.withOpacity(opacity);

  /// 获取带透明度的辅色
  static Color secondaryWithOpacity(double opacity) =>
      secondary.withOpacity(opacity);

  // ==================== 便捷访问器 ====================

  /// 次要文本色 (自适应亮色/暗色)
  static const Color textSecondary = textSecondaryLight;

  /// 禁用文本色 (自适应亮色/暗色)
  static const Color textDisabled = textDisabledLight;
}
