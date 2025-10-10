import 'package:equatable/equatable.dart';

/// 购买验证结果实体
class PurchaseResult extends Equatable {
  /// 验证是否通过
  final bool verified;

  /// 商品ID
  final String productId;

  /// 交易ID（如果验证成功）
  final String? transactionId;

  /// 权益是否已应用
  final bool benefitsApplied;

  /// 消息
  final String message;

  const PurchaseResult({
    required this.verified,
    required this.productId,
    this.transactionId,
    required this.benefitsApplied,
    required this.message,
  });

  @override
  List<Object?> get props => [
        verified,
        productId,
        transactionId,
        benefitsApplied,
        message,
      ];

  @override
  String toString() {
    return 'PurchaseResult(verified: $verified, productId: $productId, '
        'transactionId: $transactionId, benefitsApplied: $benefitsApplied, '
        'message: $message)';
  }
}
