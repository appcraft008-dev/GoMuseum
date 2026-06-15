import 'package:equatable/equatable.dart';

class UserBenefits extends Equatable {
  final bool hasAccess;
  final int recognitionQuota;
  final int referralBonusQuota;
  final int totalQuota;
  final bool isPremium;
  final bool dayPassActive;
  final int totalUsed;
  final DateTime? premiumExpiresAt;
  final DateTime? dayPassExpiresAt;

  const UserBenefits({
    required this.hasAccess,
    required this.recognitionQuota,
    required this.referralBonusQuota,
    required this.totalQuota,
    required this.isPremium,
    required this.dayPassActive,
    required this.totalUsed,
    this.premiumExpiresAt,
    this.dayPassExpiresAt,
  });

  /// 无任何权益的默认状态（加载失败时的兜底）
  factory UserBenefits.none() => const UserBenefits(
        hasAccess: false,
        recognitionQuota: 0,
        referralBonusQuota: 0,
        totalQuota: 0,
        isPremium: false,
        dayPassActive: false,
        totalUsed: 0,
      );

  UserBenefits copyWith({
    bool? hasAccess,
    int? recognitionQuota,
    int? referralBonusQuota,
    int? totalQuota,
    bool? isPremium,
    bool? dayPassActive,
    int? totalUsed,
    DateTime? premiumExpiresAt,
    DateTime? dayPassExpiresAt,
  }) {
    return UserBenefits(
      hasAccess: hasAccess ?? this.hasAccess,
      recognitionQuota: recognitionQuota ?? this.recognitionQuota,
      referralBonusQuota: referralBonusQuota ?? this.referralBonusQuota,
      totalQuota: totalQuota ?? this.totalQuota,
      isPremium: isPremium ?? this.isPremium,
      dayPassActive: dayPassActive ?? this.dayPassActive,
      totalUsed: totalUsed ?? this.totalUsed,
      premiumExpiresAt: premiumExpiresAt ?? this.premiumExpiresAt,
      dayPassExpiresAt: dayPassExpiresAt ?? this.dayPassExpiresAt,
    );
  }

  @override
  List<Object?> get props => [
        hasAccess,
        recognitionQuota,
        referralBonusQuota,
        totalQuota,
        isPremium,
        dayPassActive,
        totalUsed,
        premiumExpiresAt,
        dayPassExpiresAt,
      ];
}
