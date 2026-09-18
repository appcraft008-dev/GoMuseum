// GENERATED CODE - DO NOT MODIFY BY HAND

part of 'auto_save_photo_provider.dart';

// **************************************************************************
// RiverpodGenerator
// **************************************************************************

String _$autoSavePhotoHash() => r'56b9183599d329ee2c08f181899f839be2a09c50';

/// 拍完是否自动把照片存进系统相册。
///
/// **默认关**：往用户自己的相册里写东西必须是他主动选的。
/// 与 [Language] 同模式：初值先给默认，再异步从 SharedPreferences 载入
/// （冷启动后极短暂为 false，设置页首帧可能显示成关，可接受）。
///
/// `keepAlive`：离开设置页就销毁的话，每次回来都要重跑一遍异步载入、期间显示
/// 成关。这是个 App 生命期的偏好，不该跟着页面来回销毁。
///
/// Copied from [AutoSavePhoto].
@ProviderFor(AutoSavePhoto)
final autoSavePhotoProvider = NotifierProvider<AutoSavePhoto, bool>.internal(
  AutoSavePhoto.new,
  name: r'autoSavePhotoProvider',
  debugGetCreateSourceHash: const bool.fromEnvironment('dart.vm.product')
      ? null
      : _$autoSavePhotoHash,
  dependencies: null,
  allTransitiveDependencies: null,
);

typedef _$AutoSavePhoto = Notifier<bool>;
// ignore_for_file: type=lint
// ignore_for_file: subtype_of_sealed_class, invalid_use_of_internal_member, invalid_use_of_visible_for_testing_member, deprecated_member_use_from_same_package
