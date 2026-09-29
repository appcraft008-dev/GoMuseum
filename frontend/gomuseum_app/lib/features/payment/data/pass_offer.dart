/// 通票的**展示数据全部来自后端**(spec 2026-09-28-multi-city-expansion §3.3)。
///
/// 前端不认识任何一张具体的票:商品 ID、范围名(巴黎/荷兰)、天数、覆盖哪些馆,
/// 都是后端 `PASSES` 下发的。上新城市/新国家 = 后端加一行 + Play 建商品,**不发版**。
///
/// ⚠️ 前端**不知道范围是城市还是国家** —— `label` 只是一个名字,别据此做任何判断。
///
/// 解析遵循契约:禁止裸 `as String`,可缺字段一律 `as T? ?? 回退`。
library;

/// 一张**可以买**的票。来源:馆包 `pass`、402 的 `pass`、`/me.offers`。
class PassOffer {
  const PassOffer({
    required this.productId,
    required this.days,
    required this.label,
    this.covers = const [],
    this.stamp,
  });

  /// Play 商品 ID。购买/查价都用它。
  final String productId;
  final int days;

  /// 范围名,已按请求语言本地化(「巴黎」「オランダ」)。
  final String label;

  /// 这张票能用的馆(已按语言本地化的馆名)。卖点文案用它,不再写死四馆名。
  final List<String> covers;

  /// 票面刻印的地名(「PARIS」)。后端目前不下发 —— 留口子:哪天后端加上,
  /// 前端不用发版就能用上;没有时退回 [label] 大写(见 [stampText])。
  final String? stamp;

  String get stampText => (stamp ?? label).toUpperCase();

  /// null = 后端没给(老后端 / 这家馆暂未开售)。调用方显示「暂未开售」,
  /// **绝不回落到某张默认的票**。
  static PassOffer? fromJson(Object? json) {
    if (json is! Map) return null;
    final id = json['product_id'] as String?;
    if (id == null || id.isEmpty) return null;
    return PassOffer(
      productId: id,
      days: json['days'] as int? ?? 7,
      label: json['label'] as String? ?? '',
      covers:
          (json['covers'] as List?)?.whereType<String>().toList() ?? const [],
      stamp: json['stamp'] as String?,
    );
  }

  static List<PassOffer> listFromJson(Object? json) => json is List
      ? json.map(PassOffer.fromJson).whereType<PassOffer>().toList()
      : const [];
}

/// 用户**手里**的一张票(`/me.passes`):生效中或待激活。
class OwnedPass {
  const OwnedPass({
    required this.productId,
    required this.label,
    required this.days,
    required this.state,
    this.expiresAt,
    this.activateBy,
  });

  final String productId;
  final String label;
  final int days;
  final String state;
  final DateTime? expiresAt;
  final DateTime? activateBy;

  bool get isActive => state == 'active';
  bool get isPurchasedNotActivated => state == 'purchased_not_activated';

  static OwnedPass? fromJson(Object? json) {
    if (json is! Map) return null;
    final id = json['product_id'] as String?;
    if (id == null) return null;
    DateTime? t(String k) {
      final s = json[k] as String?;
      return s == null ? null : DateTime.tryParse(s)?.toLocal();
    }

    return OwnedPass(
      productId: id,
      label: json['label'] as String? ?? '',
      days: json['days'] as int? ?? 7,
      state: json['state'] as String? ?? 'active',
      expiresAt: t('expires_at'),
      activateBy: t('activate_by'),
    );
  }

  static List<OwnedPass> listFromJson(Object? json) => json is List
      ? json.map(OwnedPass.fromJson).whereType<OwnedPass>().toList()
      : const [];
}

/// 馆名列表按语言拼成一句(中日用顿号,其余用逗号)。
String joinMuseums(List<String> names, String languageCode) {
  final sep = (languageCode == 'zh' || languageCode == 'ja') ? '、' : ', ';
  return names.join(sep);
}
