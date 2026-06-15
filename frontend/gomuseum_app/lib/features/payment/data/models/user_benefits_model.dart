import '../../domain/entities/user_benefits.dart';

/// UserBenefits的数据模型（带JSON序列化）
class UserBenefitsModel extends UserBenefits {
  const UserBenefitsModel({
    required super.hasAccess,
    required super.recognitionQuota,
    required super.referralBonusQuota,
    required super.totalQuota,
    required super.isPremium,
    required super.dayPassActive,
    required super.totalUsed,
    super.premiumExpiresAt,
    super.dayPassExpiresAt,
  });

  /// 从JSON创建（字段对齐后端 /payment 权益响应）
  factory UserBenefitsModel.fromJson(Map<String, dynamic> json) {
    return UserBenefitsModel(
      hasAccess: json['has_access'] as bool? ?? false,
      recognitionQuota: json['recognition_quota'] as int? ?? 0,
      referralBonusQuota: json['referral_bonus_quota'] as int? ?? 0,
      totalQuota: json['total_quota'] as int? ?? 0,
      isPremium: json['is_premium'] as bool? ?? false,
      dayPassActive: json['day_pass_active'] as bool? ?? false,
      totalUsed: json['total_used'] as int? ?? 0,
      premiumExpiresAt: json['premium_expires_at'] != null
          ? DateTime.parse(json['premium_expires_at'] as String)
          : null,
      dayPassExpiresAt: json['day_pass_expires_at'] != null
          ? DateTime.parse(json['day_pass_expires_at'] as String)
          : null,
    );
  }

  /// 转换为JSON
  Map<String, dynamic> toJson() {
    return {
      'has_access': hasAccess,
      'recognition_quota': recognitionQuota,
      'referral_bonus_quota': referralBonusQuota,
      'total_quota': totalQuota,
      'is_premium': isPremium,
      'day_pass_active': dayPassActive,
      'total_used': totalUsed,
      'premium_expires_at': premiumExpiresAt?.toIso8601String(),
      'day_pass_expires_at': dayPassExpiresAt?.toIso8601String(),
    };
  }

  /// 从Entity创建Model
  factory UserBenefitsModel.fromEntity(UserBenefits entity) {
    return UserBenefitsModel(
      hasAccess: entity.hasAccess,
      recognitionQuota: entity.recognitionQuota,
      referralBonusQuota: entity.referralBonusQuota,
      totalQuota: entity.totalQuota,
      isPremium: entity.isPremium,
      dayPassActive: entity.dayPassActive,
      totalUsed: entity.totalUsed,
      premiumExpiresAt: entity.premiumExpiresAt,
      dayPassExpiresAt: entity.dayPassExpiresAt,
    );
  }
}
