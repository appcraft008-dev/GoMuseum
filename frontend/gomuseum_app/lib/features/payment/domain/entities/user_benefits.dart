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
