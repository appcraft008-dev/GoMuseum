// GENERATED CODE - DO NOT MODIFY BY HAND

part of 'benefits_provider.dart';

// **************************************************************************
// RiverpodGenerator
// **************************************************************************

String _$deviceIdHash() => r'ad8cb9dacf36c34dec13c60606e2ffd1e4b8f240';

/// 设备ID Provider
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
String _$benefitsStateHash() => r'77cd7d60b6681b454f4996aa1c717c2a20a2319a';

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
