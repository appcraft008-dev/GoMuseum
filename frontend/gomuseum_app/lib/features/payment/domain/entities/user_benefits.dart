import 'package:equatable/equatable.dart';

/// 免费层的额度账。
///
/// ⚠️ **这里没有会员/通票状态,不要往里加。** 权益真相源是服务端的 entitlements
/// (读 `/entitlements` 的 `can`)。曾经的 isPremium / dayPassActive 已随老商品
/// 下线一并移除 —— 两套并行的权益标志正是"App 显示会员却被 402 拦下"的根源。
class UserBenefits extends Equatable {
  final bool hasAccess;
  final int recognitionQuota;
  final int referralBonusQuota;
  final int totalQuota;
  final int totalUsed;

  const UserBenefits({
    required this.hasAccess,
    required this.recognitionQuota,
    required this.referralBonusQuota,
    required this.totalQuota,
    required this.totalUsed,
  });

  /// 无任何权益的默认状态（加载失败时的兜底）
  factory UserBenefits.none() => const UserBenefits(
        hasAccess: false,
        recognitionQuota: 0,
        referralBonusQuota: 0,
        totalQuota: 0,
        totalUsed: 0,
      );

  UserBenefits copyWith({
    bool? hasAccess,
    int? recognitionQuota,
    int? referralBonusQuota,
    int? totalQuota,
    int? totalUsed,
  }) {
    return UserBenefits(
      hasAccess: hasAccess ?? this.hasAccess,
      recognitionQuota: recognitionQuota ?? this.recognitionQuota,
      referralBonusQuota: referralBonusQuota ?? this.referralBonusQuota,
      totalQuota: totalQuota ?? this.totalQuota,
      totalUsed: totalUsed ?? this.totalUsed,
    );
  }

  @override
  List<Object?> get props => [
        hasAccess,
        recognitionQuota,
        referralBonusQuota,
        totalQuota,
        totalUsed,
      ];
}
