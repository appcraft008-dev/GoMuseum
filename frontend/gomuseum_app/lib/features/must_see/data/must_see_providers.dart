// lib/features/must_see/data/must_see_providers.dart
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:gomuseum_app/features/auth/presentation/auth_provider.dart';
import 'package:gomuseum_app/features/must_see/data/must_see_models.dart';
import 'package:gomuseum_app/features/settings/presentation/providers/language_provider.dart';

/// 某馆的必看护照数据(清单 + 当前轮进度 + 勋章)。
///
/// 进度随账号变 → 随账号失效(同 museumsListProvider)。autoDispose:离开页面就丢,
/// 每次进来都是最新进度;盖章提示/切到「必看」tab 时主动 invalidate。
final mustSeeProvider =
    FutureProvider.autoDispose.family<MustSeeData, String>((ref, slug) async {
  ref.watch(currentUserProvider.select((u) => u.valueOrNull?.id));
  final lang = apiLanguage(ref.watch(resolvedLocaleProvider));
  final r = await ref.watch(dioProvider).get('/api/v1/museums/$slug/must-see',
      queryParameters: {'language': lang});
  final data = r.data;
  return MustSeeData.fromJson(
      data is Map<String, dynamic> ? data : const <String, dynamic>{});
});
