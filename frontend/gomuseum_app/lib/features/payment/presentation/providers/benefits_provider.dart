import 'dart:math';

import 'package:android_id/android_id.dart';
import 'package:device_info_plus/device_info_plus.dart';
import 'package:flutter/foundation.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:in_app_purchase/in_app_purchase.dart';
import 'package:riverpod_annotation/riverpod_annotation.dart';
import 'package:gomuseum_app/core/error/failures.dart';
import '../../domain/entities/user_benefits.dart';
import 'payment_providers.dart';

part 'benefits_provider.g.dart';

/// 购买验证的结局。**`conflict` 必须与 `failed` 分开** ——
/// 前者重试永远不会成功(票归别的账号),UI 要给"换账号登录";
/// 后者是网络/服务端抖动,重试是对的。
enum VerifyOutcome { ok, failed, conflict }

const _kFallbackDeviceIdKey = 'device_id_fallback';

/// 平台标识取不到时的兜底:本地持久化一个随机 ID。
///
/// ⚠️ **绝不返回常量**。返回常量正是本次修复的 bug ——
/// 后端按 device_id 复用游客账号,所有落进同一个值的设备会被认成同一个用户,
/// 共享同一份免费额度(5 次识别 + 1 件语音)。
@visibleForTesting
Future<String> resolveFallbackDeviceId({
  required Future<String?> Function() read,
  required Future<void> Function(String) write,
}) async {
  final existing = await read();
  if (existing != null && existing.isNotEmpty) return existing;
  final rnd = Random.secure();
  final id = 'fb_'
      '${List.generate(16, (_) => rnd.nextInt(256).toRadixString(16).padLeft(2, '0')).join()}';
  await write(id);
  return id;
}

/// 设备ID Provider —— 后端据此复用游客账号(见 auth_service.guest_login)。
/// 要求:**同设备稳定、跨设备唯一**,且尽量扛卸载重装(否则免费额度可被反复刷)。
@riverpod
Future<String> deviceId(DeviceIdRef ref) async {
  try {
    if (defaultTargetPlatform == TargetPlatform.iOS) {
      // per-vendor per-device;卸载本厂商全部 app 才重置。
      final v = (await DeviceInfoPlugin().iosInfo).identifierForVendor;
      if (v != null && v.isNotEmpty) return v;
    } else if (defaultTargetPlatform == TargetPlatform.android) {
      // Settings.Secure.ANDROID_ID:每设备 × 每签名密钥唯一,卸载重装不变。
      // ⛔ **别改回 `androidInfo.id`** —— 那是 `Build.ID`(系统构建号,形如
      // TQ3A.230805.001),同一 ROM 版本的所有设备完全相同。用它当身份会让
      // 后端把成千上万个用户复用成同一个游客账号、共享一份免费额度:
      // 第一个人用完 5 次,之后所有同 ROM 的新用户打开就是 0 次。
      final v = await const AndroidId().getId();
      if (v != null && v.isNotEmpty) return v;
    }
  } catch (e) {
    debugPrint('Failed to get platform device ID: $e');
  }
  // Web / 取不到 / 抛异常 → 落一个持久化的随机 ID,而不是常量。
  const storage = FlutterSecureStorage();
  return resolveFallbackDeviceId(
    read: () => storage.read(key: _kFallbackDeviceIdKey),
    write: (v) => storage.write(key: _kFallbackDeviceIdKey, value: v),
  );
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

  /// 验证购买并更新权益。
  ///
  /// ⚠️ 返回 [VerifyOutcome] 而不是 bool:**收据冲突必须与普通失败分开**。
  /// 它是唯一一种"重试永远不会成功"的失败(票已归属别的账号),压成 false
  /// 就会显示成「购买失败,请重试」——用户点到死也不会好,最后要么重复购买、
  /// 要么申请退款。
  Future<VerifyOutcome> verifyAndUpdateBenefits(
      PurchaseDetails purchase) async {
    try {
      final deviceIdValue = await ref.read(deviceIdProvider.future);
      final verifyPurchaseUseCase = ref.read(verifyPurchaseUseCaseProvider);

      final result = await verifyPurchaseUseCase(
        purchase: purchase,
        deviceId: deviceIdValue,
        // 身份以**令牌**为准(dio 已挂 AuthInterceptor,游客也有令牌)。
        // 这里传 null 是刻意的:后端不再采信请求体里的 user_id——曾因回落到
        // device_id,把权益的 user_id 存成设备号,导致用户付了钱却查不到通票。
        userId: null,
      );

      return result.fold(
        (failure) {
          debugPrint('Purchase verification failed: ${failure.message}');
          return failure is PurchaseConflictFailure
              ? VerifyOutcome.conflict
              : VerifyOutcome.failed;
        },
        (purchaseResult) async {
          if (purchaseResult.verified && purchaseResult.benefitsApplied) {
            // 验证成功，刷新权益
            await refresh();
            return VerifyOutcome.ok;
          }
          return VerifyOutcome.failed;
        },
      );
    } catch (e) {
      debugPrint('Error verifying purchase: $e');
      return VerifyOutcome.failed;
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
        // 身份以**令牌**为准(dio 已挂 AuthInterceptor,游客也有令牌)。
        // 这里传 null 是刻意的:后端不再采信请求体里的 user_id——曾因回落到
        // device_id,把权益的 user_id 存成设备号,导致用户付了钱却查不到通票。
        userId: null,
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

  // ⚠️ 这里曾有 `hasRecognitionAccess`,用 `quota > 0 || dayPassActive ||
  // isPremium` **自行组合**权益 —— 契约明令禁止(前端只看服务端下发的 `can`,
  // 多端各拼一套必然不一致)。它零调用方,且正确的替代品早就在:
  // `Entitlements.canRecognize`(读 `/entitlements` 的 `can.recognize`)。
  // 所以直接删,不是改写。
}
