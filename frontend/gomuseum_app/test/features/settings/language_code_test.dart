import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gomuseum_app/features/settings/presentation/providers/language_provider.dart';

void main() {
  test('supportedLocales tags in order (zh-Hant distinct from zh)', () {
    expect(kSupportedLocales.map(localeTag).toList(),
        ['zh', 'en', 'fr', 'de', 'es', 'it', 'pl', 'ja', 'ko', 'zh-Hant']);
  });

  test('languageDisplayName maps each supported locale', () {
    expect(languageDisplayName(const Locale('zh')), '简体中文');
    expect(languageDisplayName(const Locale('en')), 'English');
    expect(languageDisplayName(const Locale('fr')), 'Français');
    expect(languageDisplayName(const Locale('de')), 'Deutsch');
    expect(languageDisplayName(const Locale('es')), 'Español');
    expect(languageDisplayName(const Locale('it')), 'Italiano');
    expect(languageDisplayName(const Locale('pl')), 'Polski');
    expect(languageDisplayName(const Locale('ja')), '日本語');
    expect(languageDisplayName(const Locale('ko')), '한국어');
    expect(
        languageDisplayName(
            const Locale.fromSubtags(languageCode: 'zh', scriptCode: 'Hant')),
        '繁體中文');
  });

  test('apiLanguage maps zh-Hant → zh-hant, others use languageCode', () {
    expect(
        apiLanguage(
            const Locale.fromSubtags(languageCode: 'zh', scriptCode: 'Hant')),
        'zh-hant');
    expect(apiLanguage(const Locale('zh')), 'zh');
    expect(apiLanguage(const Locale('ja')), 'ja');
    expect(apiLanguage(const Locale('en')), 'en');
  });

  test('languageDisplayName falls back to code for unknown', () {
    expect(languageDisplayName(const Locale('ru')), 'ru');
  });
}
