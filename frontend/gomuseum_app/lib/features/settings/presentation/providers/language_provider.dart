import 'package:flutter/material.dart';
import 'package:riverpod_annotation/riverpod_annotation.dart';
import 'package:shared_preferences/shared_preferences.dart';

part 'language_provider.g.dart';

/// 讲解内容支持的语言（前端写死，与后端已生成的语言集对齐）。顺序即 UI 展示顺序。
const List<Locale> kSupportedLocales = [
  Locale('zh'),
  Locale('en'),
  Locale('fr'),
  Locale('de'),
  Locale('es'),
  Locale('it'),
];

const Map<String, String> _kLanguageNames = {
  'zh': '简体中文',
  'en': 'English',
  'fr': 'Français',
  'de': 'Deutsch',
  'es': 'Español',
  'it': 'Italiano',
};

/// Locale → 展示名（未知语言回退其 code）。
String languageDisplayName(Locale locale) =>
    _kLanguageNames[locale.languageCode] ?? locale.languageCode;

@riverpod
class Language extends _$Language {
  static const String _key = 'selected_language';

  @override
  Locale build() {
    _loadLanguage();
    return const Locale('en');
  }

  Future<void> _loadLanguage() async {
    final prefs = await SharedPreferences.getInstance();
    final code = prefs.getString(_key) ?? 'en';
    state = Locale(code);
  }

  Future<void> setLanguage(Locale locale) async {
    state = locale;
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString(_key, locale.languageCode);
  }
}
