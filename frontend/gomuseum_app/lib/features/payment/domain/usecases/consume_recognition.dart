import 'package:dartz/dartz.dart';
import '../../../../core/error/failures.dart';
import '../entities/consumption_result.dart';
import '../repositories/payment_repository.dart';

/// 消耗识别配额UseCase
class ConsumeRecognition {
  final PaymentRepository repository;

  const ConsumeRecognition({required this.repository});

  /// 执行配额消耗
  ///
  /// [userId] - 用户ID（可选）
  /// [deviceId] - 设备ID
  Future<Either<Failure, ConsumptionResult>> call({
    String? userId,
    required String deviceId,
  }) async {
    // 验证设备ID
    if (deviceId.isEmpty) {
      return const Left(ValidationFailure('Device ID cannot be empty'));
    }

    // 调用仓储消耗配额
    return await repository.consumeRecognition(
      userId: userId,
      deviceId: deviceId,
    );
  }
}
