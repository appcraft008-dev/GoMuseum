import '../../domain/entities/user_benefits.dart';

/// UserBenefits的数据模型（带JSON序列化）
class UserBenefitsModel extends UserBenefits {
  const UserBenefitsModel({
    required super.hasAccess,
    required super.recognitionQuota,
    required super.referralBonusQuota,
    required super.totalQuota,
    required super.totalUsed,
  });

  /// 从JSON创建（字段对齐后端 /payment 权益响应）
  ///
  /// 全部字段带缺省兜底：后端已移除 is_premium / day_pass_active 等老字段，
  /// 少字段不会让解析崩（契约：禁止对可能缺失的字段做非空强转）。
  factory UserBenefitsModel.fromJson(Map<String, dynamic> json) {
    return UserBenefitsModel(
      hasAccess: json['has_access'] as bool? ?? false,
      recognitionQuota: json['recognition_quota'] as int? ?? 0,
      referralBonusQuota: json['referral_bonus_quota'] as int? ?? 0,
      totalQuota: json['total_quota'] as int? ?? 0,
      totalUsed: json['total_used'] as int? ?? 0,
    );
  }

  /// 转换为JSON
  Map<String, dynamic> toJson() {
    return {
      'has_access': hasAccess,
      'recognition_quota': recognitionQuota,
      'referral_bonus_quota': referralBonusQuota,
      'total_quota': totalQuota,
      'total_used': totalUsed,
    };
  }

  /// 从Entity创建Model
  factory UserBenefitsModel.fromEntity(UserBenefits entity) {
    return UserBenefitsModel(
      hasAccess: entity.hasAccess,
      recognitionQuota: entity.recognitionQuota,
      referralBonusQuota: entity.referralBonusQuota,
      totalQuota: entity.totalQuota,
      totalUsed: entity.totalUsed,
    );
  }
}
