import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gomuseum_app/features/settings/presentation/providers/language_provider.dart';

void main() {
  test('supportedLocales is zh/en/fr in order', () {
    expect(kSupportedLocales.map((l) => l.languageCode).toList(),
        ['zh', 'en', 'fr']);
  });

  test('languageDisplayName maps each supported locale', () {
    expect(languageDisplayName(const Locale('zh')), '简体中文');
    expect(languageDisplayName(const Locale('en')), 'English');
    expect(languageDisplayName(const Locale('fr')), 'Français');
  });

  test('languageDisplayName falls back to code for unknown', () {
    expect(languageDisplayName(const Locale('de')), 'de');
  });
}
