import 'package:flutter/material.dart';
import 'package:riverpod_annotation/riverpod_annotation.dart';
import 'package:shared_preferences/shared_preferences.dart';

part 'language_provider.g.dart';

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
