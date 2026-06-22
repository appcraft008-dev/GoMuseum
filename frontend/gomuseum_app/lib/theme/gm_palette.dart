// lib/theme/gm_palette.dart
import 'package:flutter/material.dart';

/// 暖纸手册「亮(B)/暗(BD)」双套设计令牌。
/// 来源：design_handoff_gomuseum/gm-shared.jsx GM_THEMES.B / GM_THEMES.BD。
@immutable
class GmPalette {
  const GmPalette({
    required this.bg,
    required this.surface,
    required this.ink,
    required this.sub,
    required this.faint,
    required this.line,
    required this.accent,
    required this.accentDeep,
    required this.ctaBg,
    required this.ctaInk,
    required this.ctaDash,
    required this.chipBg,
    required this.isDark,
  });

  final Color bg, surface, ink, sub, faint, line;
  final Color accent, accentDeep, ctaBg, ctaInk, ctaDash, chipBg;
  final bool isDark;

  static const GmPalette light = GmPalette(
    bg: Color(0xFFF3EDDF),
    surface: Color(0xFFFBF7EC),
    ink: Color(0xFF2C2316),
    sub: Color(0xFF8A7A5F),
    faint: Color(0xFFB0A283),
    line: Color(0xFFDCD2B8),
    accent: Color(0xFFA14E28),
    accentDeep: Color(0xFF7E3A1C),
    ctaBg: Color(0xFFA14E28),
    ctaInk: Color(0xFFFBF7EC),
    ctaDash: Color(0x73FBF7EC),
    chipBg: Color(0xFFEAE2CD),
    isDark: false,
  );

  static const GmPalette dark = GmPalette(
    bg: Color(0xFF201A12),
    surface: Color(0xFF2A2218),
    ink: Color(0xFFEFE6D2),
    sub: Color(0xFFA89878),
    faint: Color(0xFF6E614C),
    line: Color(0xFF3A3022),
    accent: Color(0xFFD08050),
    accentDeep: Color(0xFFE09668),
    ctaBg: Color(0xFFC26A3A),
    ctaInk: Color(0xFF241A0F),
    ctaDash: Color(0x73241A0F),
    chipBg: Color(0xFF332A1D),
    isDark: true,
  );
}
