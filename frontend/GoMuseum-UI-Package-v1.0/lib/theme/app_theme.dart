// lib/theme/app_theme.dart
import 'package:flutter/material.dart';
import 'tokens.dart';

ThemeData buildAppTheme() {
  final base = ThemeData.light(useMaterial3: true);
  return base.copyWith(
    scaffoldBackgroundColor: const Color(GMColors.bgBase),
    colorScheme: base.colorScheme.copyWith(
      primary: const Color(GMColors.brandPrimary),
      secondary: const Color(GMColors.brandAccent),
      surface: Colors.white,
      onSurface: const Color(GMColors.textPrimary),
    ),
    textTheme: base.textTheme.apply(
      bodyColor: const Color(GMColors.textPrimary),
      displayColor: const Color(GMColors.textPrimary),
    ),
    appBarTheme: const AppBarTheme(
      backgroundColor: Colors.transparent,
      foregroundColor: Color(GMColors.textPrimary),
      elevation: 0,
    ),
    bottomNavigationBarTheme: const BottomNavigationBarThemeData(
      selectedItemColor: Color(GMColors.brandPrimary),
      unselectedItemColor: Color(GMColors.textSecondary),
      backgroundColor: Colors.white,
      elevation: 8,
    ),
    dialogTheme: DialogTheme(
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.all(Radius.circular(GMRadius.lg)),
      ),
    ),
  );
}
