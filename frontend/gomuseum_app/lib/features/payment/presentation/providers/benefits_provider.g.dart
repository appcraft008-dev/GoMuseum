// GENERATED CODE - DO NOT MODIFY BY HAND

part of 'benefits_provider.dart';

// **************************************************************************
// RiverpodGenerator
// **************************************************************************

String _$deviceIdHash() => r'3aa6469de39a0272091e9e80eb04bf94fe43013b';

/// 设备ID Provider —— 后端据此复用游客账号(见 auth_service.guest_login)。
/// 要求:**同设备稳定、跨设备唯一**,且尽量扛卸载重装(否则免费额度可被反复刷)。
///
/// Copied from [deviceId].
@ProviderFor(deviceId)
final deviceIdProvider = AutoDisposeFutureProvider<String>.internal(
  deviceId,
  name: r'deviceIdProvider',
  debugGetCreateSourceHash:
      const bool.fromEnvironment('dart.vm.product') ? null : _$deviceIdHash,
  dependencies: null,
  allTransitiveDependencies: null,
);

@Deprecated('Will be removed in 3.0. Use Ref instead')
// ignore: unused_element
typedef DeviceIdRef = AutoDisposeFutureProviderRef<String>;
String _$benefitsStateHash() => r'21674c760986351cf198ea5d55338b03d3b0730e';

/// 用户权益状态Provider
///
/// Copied from [BenefitsState].
@ProviderFor(BenefitsState)
final benefitsStateProvider =
    AutoDisposeAsyncNotifierProvider<BenefitsState, UserBenefits>.internal(
  BenefitsState.new,
  name: r'benefitsStateProvider',
  debugGetCreateSourceHash: const bool.fromEnvironment('dart.vm.product')
      ? null
      : _$benefitsStateHash,
  dependencies: null,
  allTransitiveDependencies: null,
);

typedef _$BenefitsState = AutoDisposeAsyncNotifier<UserBenefits>;
// ignore_for_file: type=lint
// ignore_for_file: subtype_of_sealed_class, invalid_use_of_internal_member, invalid_use_of_visible_for_testing_member, deprecated_member_use_from_same_package
