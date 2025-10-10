import 'package:dartz/dartz.dart';
import 'package:in_app_purchase/in_app_purchase.dart';
import '../../../../core/error/failures.dart';
import '../entities/purchase_result.dart';
import '../repositories/payment_repository.dart';

/// 验证购买UseCase
class VerifyPurchase {
  final PaymentRepository repository;

  const VerifyPurchase({required this.repository});

  /// 执行购买验证
  ///
  /// [purchase] - IAP购买详情
  /// [userId] - 用户ID（可选）
  /// [deviceId] - 设备ID
  Future<Either<Failure, PurchaseResult>> call({
    required PurchaseDetails purchase,
    String? userId,
    required String deviceId,
  }) async {
    // 验证参数
    if (deviceId.isEmpty) {
      return const Left(ValidationFailure('Device ID cannot be empty'));
    }

    // 验证购买状态
    if (purchase.status != PurchaseStatus.purchased &&
        purchase.status != PurchaseStatus.restored) {
      return const Left(ValidationFailure('Invalid purchase status'));
    }

    // 调用仓储验证
    return await repository.verifyPurchase(
      purchase: purchase,
      userId: userId,
      deviceId: deviceId,
    );
  }
}
