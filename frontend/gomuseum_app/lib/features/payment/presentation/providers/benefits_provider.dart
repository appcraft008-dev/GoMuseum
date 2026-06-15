import 'package:device_info_plus/device_info_plus.dart';
import 'package:flutter/foundation.dart';
import 'package:in_app_purchase/in_app_purchase.dart';
import 'package:riverpod_annotation/riverpod_annotation.dart';
import '../../domain/entities/user_benefits.dart';
import 'payment_providers.dart';

part 'benefits_provider.g.dart';

/// 设备ID Provider
@riverpod
Future<String> deviceId(DeviceIdRef ref) async {
  final deviceInfo = DeviceInfoPlugin();

  try {
    if (defaultTargetPlatform == TargetPlatform.iOS) {
      final iosInfo = await deviceInfo.iosInfo;
      return iosInfo.identifierForVendor ?? 'unknown_ios';
    } else if (defaultTargetPlatform == TargetPlatform.android) {
      final androidInfo = await deviceInfo.androidInfo;
      return androidInfo.id;
    } else {
      // Web或其他平台，使用随机生成的ID
      return 'web_${DateTime.now().millisecondsSinceEpoch}';
    }
  } catch (e) {
    debugPrint('Failed to get device ID: $e');
    return 'unknown_device';
  }
}

/// 用户权益状态Provider
@riverpod
class BenefitsState extends _$BenefitsState {
  @override
  FutureOr<UserBenefits> build() async {
    // 初始化时自动加载权益
    return await _loadBenefits();
  }

  /// 加载用户权益
  Future<UserBenefits> _loadBenefits() async {
    final deviceIdValue = await ref.read(deviceIdProvider.future);
    final getUserBenefitsUseCase = ref.read(getUserBenefitsUseCaseProvider);

    final result = await getUserBenefitsUseCase(
      deviceId: deviceIdValue,
      userId: null, // 目前支持匿名用户
    );

    return result.fold(
      (failure) {
        debugPrint('Failed to load benefits: ${failure.message}');
        // 返回默认无权益状态
        return UserBenefits.none();
      },
      (benefits) => benefits,
    );
  }

  /// 刷新权益
  Future<void> refresh() async {
    state = const AsyncValue.loading();
    state = await AsyncValue.guard(() => _loadBenefits());
  }

  /// 验证购买并更新权益
  Future<bool> verifyAndUpdateBenefits(PurchaseDetails purchase) async {
    try {
      final deviceIdValue = await ref.read(deviceIdProvider.future);
      final verifyPurchaseUseCase = ref.read(verifyPurchaseUseCaseProvider);

      final result = await verifyPurchaseUseCase(
        purchase: purchase,
        deviceId: deviceIdValue,
        userId: null, // 目前支持匿名用户
      );

      return result.fold(
        (failure) {
          debugPrint('Purchase verification failed: ${failure.message}');
          return false;
        },
        (purchaseResult) async {
          if (purchaseResult.verified && purchaseResult.benefitsApplied) {
            // 验证成功，刷新权益
            await refresh();
            return true;
          }
          return false;
        },
      );
    } catch (e) {
      debugPrint('Error verifying purchase: $e');
      return false;
    }
  }

  /// 消耗识别配额
  Future<bool> consumeQuota() async {
    try {
      final deviceIdValue = await ref.read(deviceIdProvider.future);
      final consumeRecognitionUseCase =
          ref.read(consumeRecognitionUseCaseProvider);

      final result = await consumeRecognitionUseCase(
        deviceId: deviceIdValue,
        userId: null, // 目前支持匿名用户
      );

      return result.fold(
        (failure) {
          debugPrint('Failed to consume quota: ${failure.message}');
          return false;
        },
        (consumptionResult) async {
          if (consumptionResult.success) {
            // 消耗成功，更新本地状态
            final currentBenefits = state.value;
            if (currentBenefits != null) {
              // 后端 remaining_quota 即总剩余额度，UI 展示读 totalQuota
              state = AsyncValue.data(
                currentBenefits.copyWith(
                  recognitionQuota: consumptionResult.remainingQuota,
                  totalQuota: consumptionResult.remainingQuota,
                  totalUsed: currentBenefits.totalUsed + 1,
                ),
              );
            }
            return true;
          }
          return false;
        },
      );
    } catch (e) {
      debugPrint('Error consuming quota: $e');
      return false;
    }
  }

  /// 检查是否有识别权限
  bool get hasRecognitionAccess {
    final benefits = state.value;
    if (benefits == null) return false;

    // 有配额、日卡激活或高级会员，都可以识别
    return benefits.recognitionQuota > 0 ||
        benefits.dayPassActive ||
        benefits.isPremium;
  }
}
