// GENERATED CODE - DO NOT MODIFY BY HAND

part of 'explanation_provider.dart';

// **************************************************************************
// RiverpodGenerator
// **************************************************************************

String _$explanationNotifierHash() =>
    r'b1c0fc6884e6e761b39c6cf3ab63ec279822f6b7';

/// 解释功能状态管理Notifier
///
/// 负责处理解释生成的业务逻辑和状态转换。
/// 使用Riverpod的NotifierProvider模式，支持自动依赖注入。
///
/// Copied from [ExplanationNotifier].
@ProviderFor(ExplanationNotifier)
final explanationNotifierProvider =
    AutoDisposeNotifierProvider<ExplanationNotifier, ExplanationState>.internal(
  ExplanationNotifier.new,
  name: r'explanationNotifierProvider',
  debugGetCreateSourceHash: const bool.fromEnvironment('dart.vm.product')
      ? null
      : _$explanationNotifierHash,
  dependencies: null,
  allTransitiveDependencies: null,
);

typedef _$ExplanationNotifier = AutoDisposeNotifier<ExplanationState>;
// ignore_for_file: type=lint
// ignore_for_file: subtype_of_sealed_class, invalid_use_of_internal_member, invalid_use_of_visible_for_testing_member, deprecated_member_use_from_same_package
