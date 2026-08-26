import 'package:flutter/material.dart';
import 'package:riverpod_annotation/riverpod_annotation.dart';
import 'package:shared_preferences/shared_preferences.dart';

part 'language_provider.g.dart';

/// 讲解内容支持的语言（前端写死，与后端 DEFAULT_LANGUAGES 对齐）。
/// 繁体中文用带 scriptCode 的 locale（Flutter 本地化按 zh-Hant 解析 app_zh_Hant.arb）。
///
/// **顺序 = 展示名的字母序**（拉丁 A–Z 在前，CJK 在后，即码点序）。
/// 有了「跟随系统」默认值之后，会打开这个列表的人是"系统语言不是我要的"那批 ——
/// 他们已经知道要找哪个，所以**可预测 > 猜他们想要什么**（iOS/Android 系统语言
/// 设置同样是字母序）。⚠️ 加新语言时按字母序插入，别追加到末尾 —— 有测试断言。
/// ⛔ 别按"客流量"排：那需要持续维护，且排序理由无处记录，下个人只会看到一串
/// 没有规律的顺序。
const List<Locale> kSupportedLocales = [
  Locale('de'), // Deutsch
  Locale('en'), // English
  Locale('es'), // Español
  Locale('fr'), // Français
  Locale('it'), // Italiano
  Locale('pl'), // Polski
  Locale('ja'), // 日本語
  Locale('zh'), // 简体中文
  Locale.fromSubtags(languageCode: 'zh', scriptCode: 'Hant'), // 繁體中文
  Locale('ko'), // 한국어
];

/// 传给 `MaterialApp.supportedLocales` 的**解析顺序**（区别于上面的展示顺序）。
///
/// ⚠️ **首项即回退目标**：设备语言匹配不上任何一项时，Flutter 的
/// `basicLocaleListResolution` 返回 `supportedLocales.first`。
/// 「系统语言不支持 → 回退英文」这条需求**全靠它**，没有别的代码在兜底。
/// 有测试断言首项是 en、且两个列表内容一致（加语言时别只加一处）。
const List<Locale> kAppLocalesInResolutionOrder = [
  Locale('en'), // ← 回退目标，必须在首位
  Locale('zh'),
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

/// 设置项要显示的文本：`null`（跟随系统）时用调用方给的本地化文案。
String languageSettingLabel(Locale? locale, String followSystemLabel) =>
    locale == null ? followSystemLabel : languageDisplayName(locale);

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

/// UI 语言。**`null` = 跟随系统**，也是未选择过的用户的默认值。
///
/// `null` 传给 `MaterialApp.locale` 就是 Flutter 原生的跟随系统行为:框架拿设备
/// 语言去匹配 `supportedLocales`,匹配不上则回退 `supportedLocales.first`。
/// 那一项是 `Locale('en')`,所以**「系统语言不支持则回退英文」是免费的**,
/// 不需要我们写任何判断。⚠️ 别调换 main.dart 里 supportedLocales 的顺序 ——
/// 有测试断言首项是 en。
/// **实际生效**的 UI 语言（永不为 null）。
///
/// `languageProvider` 存的是用户*偏好*，跟随系统时为 null；而发给后端的
/// `language` 参数、以及任何需要"现在到底是哪种语言"的地方，要的是*生效值*。
/// 跟随系统时用 Flutter 自己的 `basicLocaleListResolution` 解析设备语言 ——
/// **与 MaterialApp 内部走的是同一个函数**，所以 UI 语言和请求语言不会分叉。
@riverpod
Locale resolvedLocale(ResolvedLocaleRef ref) {
  final chosen = ref.watch(languageProvider);
  if (chosen != null) return chosen;
  return basicLocaleListResolution(
    WidgetsBinding.instance.platformDispatcher.locales,
    kAppLocalesInResolutionOrder,
  );
}

@riverpod
class Language extends _$Language {
  static const String _key = 'selected_language';

  @override
  Locale? build() {
    _loadLanguage();
    return null;
  }

  Future<void> _loadLanguage() async {
    final prefs = await SharedPreferences.getInstance();
    final tag = prefs.getString(_key);
    if (tag != null && tag.isNotEmpty) state = _localeFromTag(tag);
  }

  /// 传 `null` 表示跟随系统 —— 此时**删掉 key** 而不是存一个哨兵值:
  /// "没有明确选择"本身就是这个状态的准确表示,也让老用户的读取路径零改动。
  Future<void> setLanguage(Locale? locale) async {
    state = locale;
    final prefs = await SharedPreferences.getInstance();
    if (locale == null) {
      await prefs.remove(_key);
      return;
    }
    // 存完整 tag（zh-Hant），而非仅 languageCode，否则繁体读回丢 scriptCode。
    await prefs.setString(_key, localeTag(locale));
  }
}
