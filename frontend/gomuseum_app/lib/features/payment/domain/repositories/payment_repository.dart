import 'package:dartz/dartz.dart';
import '../../../../core/error/failures.dart';
import '../entities/user_benefits.dart';

abstract class PaymentRepository {
  Future<Either<Failure, bool>> verifyPurchase({
    required String platform,
    required String receiptData,
    required String productId,
    String? userId,
    String? deviceId,
  });

  Future<Either<Failure, UserBenefits>> getUserBenefits({
    String? userId,
    String? deviceId,
  });

  Future<Either<Failure, int>> consumeRecognition({
    String? userId,
    String? deviceId,
  });
}
