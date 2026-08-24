// GENERATED CODE - DO NOT MODIFY BY HAND

part of 'language_provider.dart';

// **************************************************************************
// RiverpodGenerator
// **************************************************************************

String _$resolvedLocaleHash() => r'997e8a4e5ab9652ba1d136cf06e9924568df14fc';

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
///
/// Copied from [resolvedLocale].
@ProviderFor(resolvedLocale)
final resolvedLocaleProvider = AutoDisposeProvider<Locale>.internal(
  resolvedLocale,
  name: r'resolvedLocaleProvider',
  debugGetCreateSourceHash: const bool.fromEnvironment('dart.vm.product')
      ? null
      : _$resolvedLocaleHash,
  dependencies: null,
  allTransitiveDependencies: null,
);

@Deprecated('Will be removed in 3.0. Use Ref instead')
// ignore: unused_element
typedef ResolvedLocaleRef = AutoDisposeProviderRef<Locale>;
String _$languageHash() => r'c28d26e3a65dd8be855efa15917857116c9e0c3a';

/// See also [Language].
@ProviderFor(Language)
final languageProvider =
    AutoDisposeNotifierProvider<Language, Locale?>.internal(
  Language.new,
  name: r'languageProvider',
  debugGetCreateSourceHash:
      const bool.fromEnvironment('dart.vm.product') ? null : _$languageHash,
  dependencies: null,
  allTransitiveDependencies: null,
);

typedef _$Language = AutoDisposeNotifier<Locale?>;
// ignore_for_file: type=lint
// ignore_for_file: subtype_of_sealed_class, invalid_use_of_internal_member, invalid_use_of_visible_for_testing_member, deprecated_member_use_from_same_package
