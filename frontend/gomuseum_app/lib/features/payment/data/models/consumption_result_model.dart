import '../../domain/entities/consumption_result.dart';

/// ConsumptionResult的数据模型（带JSON序列化）
class ConsumptionResultModel extends ConsumptionResult {
  const ConsumptionResultModel({
    required super.success,
    required super.message,
    required super.remainingQuota,
  });

  /// 从JSON创建
  factory ConsumptionResultModel.fromJson(Map<String, dynamic> json) {
    return ConsumptionResultModel(
      success: json['success'] as bool? ?? false,
      message: json['message'] as String? ?? '',
      remainingQuota: json['remaining_quota'] as int? ?? 0,
    );
  }

  /// 转换为JSON
  Map<String, dynamic> toJson() {
    return {
      'success': success,
      'message': message,
      'remaining_quota': remainingQuota,
    };
  }

  /// 从Entity创建Model
  factory ConsumptionResultModel.fromEntity(ConsumptionResult entity) {
    return ConsumptionResultModel(
      success: entity.success,
      message: entity.message,
      remainingQuota: entity.remainingQuota,
    );
  }
}
