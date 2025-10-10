import 'package:dartz/dartz.dart';
import '../../../../core/error/failures.dart';
import '../entities/user_benefits.dart';
import '../repositories/payment_repository.dart';

/// 获取用户权益UseCase
class GetUserBenefits {
  final PaymentRepository repository;

  const GetUserBenefits({required this.repository});

  /// 执行获取权益
  ///
  /// [userId] - 用户ID（可选，支持匿名用户）
  /// [deviceId] - 设备ID
  Future<Either<Failure, UserBenefits>> call({
    String? userId,
    required String deviceId,
  }) async {
    // 验证设备ID
    if (deviceId.isEmpty) {
      return const Left(ValidationFailure('Device ID cannot be empty'));
    }

    // 调用仓储获取权益
    return await repository.getUserBenefits(
      userId: userId,
      deviceId: deviceId,
    );
  }
}
