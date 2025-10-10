/// GoMuseum 尺寸和间距系统
/// 基于 8dp 网格系统
library;

class AppDimensions {
  AppDimensions._();

  // ==================== 间距 ====================
  static const double spacing4 = 4.0;
  static const double spacing8 = 8.0;
  static const double spacing12 = 12.0;
  static const double spacing16 = 16.0;
  static const double spacing24 = 24.0;
  static const double spacing32 = 32.0;
  static const double spacing40 = 40.0;
  static const double spacing48 = 48.0;

  // ==================== 圆角 ====================
  static const double radiusSmall = 8.0;
  static const double radiusMedium = 12.0;
  static const double radiusLarge = 16.0;
  static const double radiusXLarge = 24.0;
  static const double radiusRound = 999.0;

  // ==================== 组件尺寸 ====================
  static const double buttonHeight = 48.0;
  static const double buttonHeightSmall = 40.0;
  static const double iconSize = 24.0;
  static const double iconSizeLarge = 32.0;
  static const double avatarSize = 40.0;

  // ==================== 布局 ====================
  static const double pageHorizontalPadding = 16.0;
  static const double cardElevation = 2.0;
  static const double bottomNavHeight = 60.0;
}
