import '../../domain/entities/user_benefits.dart';

/// UserBenefits的数据模型（带JSON序列化）
class UserBenefitsModel extends UserBenefits {
  const UserBenefitsModel({
    required super.hasAccess,
    required super.recognitionQuota,
    required super.isPremium,
    required super.dayPassActive,
    super.dayPassExpiry,
    super.premiumExpiry,
  });

  /// 从JSON创建
  factory UserBenefitsModel.fromJson(Map<String, dynamic> json) {
    return UserBenefitsModel(
      hasAccess: json['has_access'] as bool? ?? false,
      recognitionQuota: json['recognition_quota'] as int? ?? 0,
      isPremium: json['is_premium'] as bool? ?? false,
      dayPassActive: json['day_pass_active'] as bool? ?? false,
      dayPassExpiry: json['day_pass_expiry'] != null
          ? DateTime.parse(json['day_pass_expiry'] as String)
          : null,
      premiumExpiry: json['premium_expiry'] != null
          ? DateTime.parse(json['premium_expiry'] as String)
          : null,
    );
  }

  /// 转换为JSON
  Map<String, dynamic> toJson() {
    return {
      'has_access': hasAccess,
      'recognition_quota': recognitionQuota,
      'is_premium': isPremium,
      'day_pass_active': dayPassActive,
      'day_pass_expiry': dayPassExpiry?.toIso8601String(),
      'premium_expiry': premiumExpiry?.toIso8601String(),
    };
  }

  /// 从Entity创建Model
  factory UserBenefitsModel.fromEntity(UserBenefits entity) {
    return UserBenefitsModel(
      hasAccess: entity.hasAccess,
      recognitionQuota: entity.recognitionQuota,
      isPremium: entity.isPremium,
      dayPassActive: entity.dayPassActive,
      dayPassExpiry: entity.dayPassExpiry,
      premiumExpiry: entity.premiumExpiry,
    );
  }
}
