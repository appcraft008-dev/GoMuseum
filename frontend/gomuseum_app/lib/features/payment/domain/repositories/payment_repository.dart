import 'package:dartz/dartz.dart';
import 'package:in_app_purchase/in_app_purchase.dart';
import '../../../../core/error/failures.dart';
import '../entities/consumption_result.dart';
import '../entities/purchase_result.dart';
import '../entities/user_benefits.dart';

abstract class PaymentRepository {
  /// 验证 IAP 购买并发放权益
  Future<Either<Failure, PurchaseResult>> verifyPurchase({
    required PurchaseDetails purchase,
    String? userId,
    required String deviceId,
  });

  /// 查询用户权益（配额 / 日卡 / 订阅）
  Future<Either<Failure, UserBenefits>> getUserBenefits({
    String? userId,
    required String deviceId,
  });

  /// 消耗一次识别配额
  Future<Either<Failure, ConsumptionResult>> consumeRecognition({
    String? userId,
    required String deviceId,
  });
}
