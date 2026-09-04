/// 票据历史(对应后端 `GET /api/v1/entitlements/history`)。
///
/// 权益页的「购买记录」和「上一张票」用它。**与 `/me` 分开**:`/me` 是热路径
/// (每次权益判断都调),历史只有权益页要看。
///
/// ⚠️ **这里没有金额**。`purchases.amount` 后端从来没写过(恒 NULL),而拿商店
/// 的当前售价顶替是错的 —— 那是"现在卖多少"不是"当时付了多少",涨一次价
/// 收据就开始说谎。要真金额得改购买上报链路,那条链路只能真机真购买验收。
library;

import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'package:gomuseum_app/features/auth/presentation/auth_provider.dart';

class PassRecord {
  const PassRecord({
    required this.productId,
    required this.state,
    this.purchasedAt,
    this.activatedAt,
    this.expiresAt,
  });

  final String productId;

  /// 这张票**各自的**结局:active / purchased_not_activated / expired /
  /// refunded / revoked。注意它不是"当前哪张票说了算"——那是 `/me` 的事。
  final String state;

  final DateTime? purchasedAt;
  final DateTime? activatedAt;
  final DateTime? expiresAt;

  bool get isExpired => state == 'expired';

  /// 用完的票才有完整的起止区间(「上一张已用完 · X – Y」要两头都在)。
  bool get hasRunItsCourse =>
      isExpired && activatedAt != null && expiresAt != null;

  /// **买了却从没激活,窗口过了作废。** 与 [hasRunItsCourse] 是同为"已到期"的
  /// 两种不同经历,不能混着说:前者是 7 天用完了,后者一天都没用过 ——
  /// 对后者说「7 天已经用完」是睁眼说瞎话。
  ///
  /// 曾经权益页只认 [hasRunItsCourse],这类票被整个过滤掉,页面退回未购态:
  /// 用户付了钱、票被作废,界面却表现得像他从没买过。撞契约 I20
  /// (没收已付款项必须先披露)—— 事前披露了,事后什么都不说。
  bool get lapsedUnactivated => isExpired && activatedAt == null;

  /// 契约:可缺字段一律 `as T? ?? 回退`,不裸取。
  factory PassRecord.fromJson(Map<String, dynamic> json) {
    // `.toLocal()`:后端发 UTC,不转的话 l10n 会按 UTC 渲染,票面时间比
    // 用户的钟慢 2 小时(CEST)。同 Entitlements.fromJson。
    DateTime? at(String key) {
      final raw = json[key] as String?;
      return raw == null ? null : DateTime.tryParse(raw)?.toLocal();
    }

    return PassRecord(
      productId: json['product_id'] as String? ?? '',
      state: json['state'] as String? ?? 'expired',
      purchasedAt: at('purchased_at'),
      activatedAt: at('activated_at'),
      expiresAt: at('expires_at'),
    );
  }
}

/// 新到旧。拿不到就是空列表 —— 历史读不到不该把权益页打死,
/// 那几个信息块少显示就是了。
final passHistoryProvider = FutureProvider<List<PassRecord>>((ref) async {
  // 同 entitlementsProvider:per-user 数据必须依赖用户身份,否则换账号后
  // 新用户会看到上一个账号的购买记录。
  ref.watch(currentUserProvider.select((u) => u.valueOrNull?.id));
  final dio = ref.watch(dioProvider);
  try {
    final res = await dio.get('/api/v1/entitlements/history');
    final list = (res.data as Map<String, dynamic>)['passes'] as List? ?? [];
    return list
        .whereType<Map<String, dynamic>>()
        .map(PassRecord.fromJson)
        .toList();
  } on DioException {
    return const [];
  }
});
