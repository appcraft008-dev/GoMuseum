import 'package:equatable/equatable.dart';

/// 配额消耗结果实体
class ConsumptionResult extends Equatable {
  /// 消耗是否成功
  final bool success;

  /// 消息
  final String message;

  /// 剩余配额
  final int remainingQuota;

  const ConsumptionResult({
    required this.success,
    required this.message,
    required this.remainingQuota,
  });

  @override
  List<Object?> get props => [success, message, remainingQuota];

  @override
  String toString() {
    return 'ConsumptionResult(success: $success, message: $message, '
        'remainingQuota: $remainingQuota)';
  }
}
