/// 统一权益(对应后端 `/api/v1/entitlements/me`)。
///
/// ⚠️ **前端不得自行组合 is_premium / day_pass_active / expires_at / quota 判断**——
/// 多端各写一套必然不一致(过期没关、退款没撤、恢复购买错位)。一律读这里的 `can`。
///
/// 解析遵循契约:**禁止裸 `as String`**,可缺字段一律 `as T? ?? 回退`。
library;

import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'package:gomuseum_app/features/auth/presentation/auth_provider.dart';

/// 权益状态。与后端 entitlement_service 的常量一一对应。
class Entitlements {
  const Entitlements({
    required this.state,
    required this.canPurchase,
    required this.canRecognize,
    required this.canAudioAny,
    required this.canAiAsk,
    this.expiresAt,
    this.freeRecognitionsLeft,
    this.freeRecognitionsTotal,
    this.freeAudioQid,
  });

  final String state;

  /// 能否直接购买。**买票前必须登录**:通票挂 user_id,而游客身份是设备绑定的,
  /// 游客买了票换手机就永久拿不回(收据已消耗,恢复购买命中幂等)。
  /// 由后端给,前端不自己拼身份判断(契约:前端只看 can)。
  final bool canPurchase;
  final bool canRecognize;
  final bool canAudioAny;
  final bool canAiAsk;
  final DateTime? expiresAt;

  /// 免费层剩余识别次数;通票生效期间为 null(不显示次数)。
  final int? freeRecognitionsLeft;

  /// 进度环的分母,由后端给 —— 别在前端写死(曾写死 10,后端调 5 后显示 "5/10")。
  final int? freeRecognitionsTotal;

  /// 已认领的首件免费语音 qid。该件可无限重播,其余需通票。
  final String? freeAudioQid;

  /// 通票是否生效中。
  bool get isActive => state == 'active';

  /// 已购但未开始计时(旅游产品:用户常提前几天买)。
  bool get isPurchasedNotActivated => state == 'purchased_not_activated';

  /// 某件的语音能不能放:通票内全放,免费用户只放已认领的首件。
  bool canPlayAudio(String qid) =>
      canAudioAny || (freeAudioQid != null && freeAudioQid == qid);

  /// 拿不到权益时的保守回退:按免费层算,次数未知。
  /// 不假装有通票(失败时放行付费功能=白送),也不假装 0 次(会误弹付费墙)。
  static const Entitlements unknown = Entitlements(
    state: 'not_purchased',
    canPurchase: false,
    canRecognize: true,
    canAudioAny: false,
    canAiAsk: false,
  );

  factory Entitlements.fromJson(Map<String, dynamic> json) {
    final can = json['can'] as Map<String, dynamic>? ?? const {};
    final expires = json['expires_at'] as String?;
    return Entitlements(
      state: json['state'] as String? ?? 'not_purchased',
      // 缺字段时保守取 false:宁可多引导一次登录,也不要让游客买了票丢票
      canPurchase: can['purchase'] == true,
      canRecognize: can['recognize'] as bool? ?? true,
      canAudioAny: can['audio_any'] as bool? ?? false,
      canAiAsk: can['ai_ask'] as bool? ?? false,
      expiresAt: expires == null ? null : DateTime.tryParse(expires),
      freeRecognitionsLeft: json['free_recognitions_left'] as int?,
      freeRecognitionsTotal: json['free_recognitions_total'] as int?,
      freeAudioQid: json['free_audio_qid'] as String?,
    );
  }
}

/// 当前用户权益。user_id 由后端从令牌取(dioProvider 已挂 AuthInterceptor),
/// **不传查询参数** —— 传 user_id 等于谁都能读别人权益、烧别人的票。
final entitlementsProvider = FutureProvider<Entitlements>((ref) async {
  final dio = ref.watch(dioProvider);
  try {
    final res = await dio.get('/api/v1/entitlements/me');
    return Entitlements.fromJson(res.data as Map<String, dynamic>);
  } on DioException {
    // 离线/后端抖动不该把界面打死,按免费层展示(次数显示 "—")
    return Entitlements.unknown;
  }
});

/// 激活通票:**买了不立即计时**(旅游产品用户常提前几天买),首次使用高级功能
/// 且用户**显式确认**后才开始连续 7×24h。幂等——再调不续期也不重置。
///
/// ⚠️ 这一步此前完全没有触发器:后端设计了 purchased_not_activated 状态,
/// 但没有任何客户端调 /activate,于是 `can.audio_any = (state == active)` 恒为
/// false —— 用户付了 €7.99 依然被付费墙拦住。
Future<Entitlements?> activatePass(WidgetRef ref) async {
  final dio = ref.read(dioProvider);
  try {
    final res = await dio.post('/api/v1/entitlements/activate');
    return Entitlements.fromJson(res.data as Map<String, dynamic>);
  } on DioException {
    return null;
  }
}
