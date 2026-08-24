import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gomuseum_app/features/settings/presentation/providers/language_provider.dart';

void main() {
  // 断言的是「十种语言齐全，且 zh-Hant 与 zh 是两个不同的 tag」这个性质。
  // ⛔ 别改回硬编码顺序数组：展示顺序按字母序排，由
  // language_follow_system_test 的排序断言负责，两处写死会互相打架。
  test('supportedLocales tags complete (zh-Hant distinct from zh)', () {
    expect(kSupportedLocales.map(localeTag).toSet(),
        {'zh', 'en', 'fr', 'de', 'es', 'it', 'pl', 'ja', 'ko', 'zh-Hant'});
    expect(kSupportedLocales.length, 10); // 无重复
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
