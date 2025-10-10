import '../../domain/entities/purchase_result.dart';

/// PurchaseResult的数据模型（带JSON序列化）
class PurchaseResultModel extends PurchaseResult {
  const PurchaseResultModel({
    required super.verified,
    required super.productId,
    super.transactionId,
    required super.benefitsApplied,
    required super.message,
  });

  /// 从JSON创建
  factory PurchaseResultModel.fromJson(Map<String, dynamic> json) {
    return PurchaseResultModel(
      verified: json['verified'] as bool? ?? false,
      productId: json['product_id'] as String? ?? '',
      transactionId: json['transaction_id'] as String?,
      benefitsApplied: json['benefits_applied'] as bool? ?? false,
      message: json['message'] as String? ?? '',
    );
  }

  /// 转换为JSON
  Map<String, dynamic> toJson() {
    return {
      'verified': verified,
      'product_id': productId,
      'transaction_id': transactionId,
      'benefits_applied': benefitsApplied,
      'message': message,
    };
  }

  /// 从Entity创建Model
  factory PurchaseResultModel.fromEntity(PurchaseResult entity) {
    return PurchaseResultModel(
      verified: entity.verified,
      productId: entity.productId,
      transactionId: entity.transactionId,
      benefitsApplied: entity.benefitsApplied,
      message: entity.message,
    );
  }
}
