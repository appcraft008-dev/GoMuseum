import 'package:flutter/material.dart';
import 'package:riverpod_annotation/riverpod_annotation.dart';
import 'package:shared_preferences/shared_preferences.dart';

part 'language_provider.g.dart';

/// 支持的语言列表
enum SupportedLanguage {
  english('en', 'English', '🇬🇧'),
  french('fr', 'Français', '🇫🇷'),
  german('de', 'Deutsch', '🇩🇪'),
  spanish('es', 'Español', '🇪🇸'),
  italian('it', 'Italiano', '🇮🇹'),
  chinese('zh', '中文', '🇨🇳');

  const SupportedLanguage(this.code, this.name, this.flag);

  final String code;
  final String name;
  final String flag;

  /// 从语言代码获取枚举值
  static SupportedLanguage fromCode(String code) {
    return SupportedLanguage.values.firstWhere(
      (lang) => lang.code == code,
      orElse: () => SupportedLanguage.english,
    );
  }
}

/// 语言设置状态
class LanguageState {
  final SupportedLanguage language;
  final Locale locale;

  const LanguageState({
    required this.language,
    required this.locale,
  });

  LanguageState copyWith({
    SupportedLanguage? language,
    Locale? locale,
  }) {
    return LanguageState(
      language: language ?? this.language,
      locale: locale ?? this.locale,
    );
  }
}

/// 语言设置Notifier
@riverpod
class LanguageNotifier extends _$LanguageNotifier {
  static const String _languageKey = 'app_language';

  @override
  LanguageState build() {
    // 初始化时从SharedPreferences加载
    _loadLanguage();
    return const LanguageState(
      language: SupportedLanguage.english,
      locale: Locale('en'),
    );
  }

  /// 从本地存储加载语言设置
  Future<void> _loadLanguage() async {
    try {
      final prefs = await SharedPreferences.getInstance();
      final languageCode = prefs.getString(_languageKey);

      if (languageCode != null) {
        final language = SupportedLanguage.fromCode(languageCode);
        state = LanguageState(
          language: language,
          locale: Locale(language.code),
        );
      }
    } catch (e) {
      // 如果加载失败，使用默认语言
      debugPrint('Failed to load language: $e');
    }
  }

  /// 设置语言
  Future<void> setLanguage(SupportedLanguage language) async {
    try {
      // 更新状态
      state = LanguageState(
        language: language,
        locale: Locale(language.code),
      );

      // 保存到本地存储
      final prefs = await SharedPreferences.getInstance();
      await prefs.setString(_languageKey, language.code);

      debugPrint('Language set to: ${language.name}');
    } catch (e) {
      debugPrint('Failed to save language: $e');
    }
  }

  /// 获取当前语言代码（用于API调用）
  String get currentLanguageCode => state.language.code;

  /// 获取当前Locale（用于UI）
  Locale get currentLocale => state.locale;
}
