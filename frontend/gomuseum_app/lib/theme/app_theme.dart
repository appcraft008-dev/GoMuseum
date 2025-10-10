/// GoMuseum 主题配置
library;

import 'package:flutter/material.dart';
import 'colors.dart';
import 'typography.dart';
import 'dimensions.dart';

class AppTheme {
  AppTheme._();

  static ThemeData lightTheme() {
    return ThemeData(
      useMaterial3: true,
      brightness: Brightness.light,
      colorScheme: ColorScheme.light(
        primary: AppColors.primary,
        onPrimary: Colors.white,
        secondary: AppColors.secondary,
      ),
      textTheme: AppTypography.lightTextTheme,
    );
  }

  static ThemeData darkTheme() {
    return ThemeData(
      useMaterial3: true,
      brightness: Brightness.dark,
      colorScheme: ColorScheme.dark(
        primary: AppColors.primaryLight,
        secondary: AppColors.secondaryLight,
      ),
      textTheme: AppTypography.darkTextTheme,
    );
  }
}
