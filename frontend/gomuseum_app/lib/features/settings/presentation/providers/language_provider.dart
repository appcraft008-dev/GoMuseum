import 'package:flutter/material.dart';
import 'package:riverpod_annotation/riverpod_annotation.dart';
import 'package:shared_preferences/shared_preferences.dart';

part 'language_provider.g.dart';

/// 讲解内容支持的语言（前端写死，与后端 DEFAULT_LANGUAGES 对齐）。顺序即 UI 展示顺序。
/// 繁体中文用带 scriptCode 的 locale（Flutter 本地化按 zh-Hant 解析 app_zh_Hant.arb）。
const List<Locale> kSupportedLocales = [
  Locale('zh'),
  Locale('en'),
  Locale('fr'),
  Locale('de'),
  Locale('es'),
  Locale('it'),
  Locale('pl'),
  Locale('ja'),
  Locale('ko'),
  Locale.fromSubtags(languageCode: 'zh', scriptCode: 'Hant'),
];

/// 展示名按**完整 tag**查（区分 zh=简体 / zh-Hant=繁体，避免键冲突）。
const Map<String, String> _kLanguageNames = {
  'zh': '简体中文',
  'zh-Hant': '繁體中文',
  'en': 'English',
  'fr': 'Français',
  'de': 'Deutsch',
  'es': 'Español',
  'it': 'Italiano',
  'pl': 'Polski',
  'ja': '日本語',
  'ko': '한국어',
};

/// Locale → 展示名（先按完整 tag，再退 languageCode，末退 code 本身）。
String languageDisplayName(Locale locale) =>
    _kLanguageNames[localeTag(locale)] ??
    _kLanguageNames[locale.languageCode] ??
    locale.languageCode;

/// 发给后端 API 的 `language` 参数：繁体中文映射到 `zh-hant`（后端 zh 与 zh-hant
/// 是两套），其余直接用 languageCode。**所有 API 语言取值处必须走此函数。**
String apiLanguage(Locale l) =>
    (l.languageCode == 'zh' && l.scriptCode == 'Hant')
        ? 'zh-hant'
        : l.languageCode;

/// 完整 language tag（含 scriptCode），用于持久化与展示名键：zh-Hant / en / ja…
String localeTag(Locale l) => l.toLanguageTag();

/// tag → Locale（还原 scriptCode，避免繁体 round-trip 丢 Hant）。
Locale _localeFromTag(String tag) {
  final parts = tag.split('-');
  if (parts.length >= 2) {
    return Locale.fromSubtags(languageCode: parts.first, scriptCode: parts[1]);
  }
  return Locale(tag);
}

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
    final tag = prefs.getString(_key);
    if (tag != null && tag.isNotEmpty) state = _localeFromTag(tag);
  }

  Future<void> setLanguage(Locale locale) async {
    state = locale;
    final prefs = await SharedPreferences.getInstance();
    // 存完整 tag（zh-Hant），而非仅 languageCode，否则繁体读回丢 scriptCode。
    await prefs.setString(_key, localeTag(locale));
  }
}
