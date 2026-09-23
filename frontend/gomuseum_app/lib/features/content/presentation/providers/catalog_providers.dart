// lib/features/content/presentation/providers/catalog_providers.dart
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:gomuseum_app/features/auth/presentation/auth_provider.dart';
import 'package:gomuseum_app/features/content/data/datasources/catalog_remote_datasource.dart';
import 'package:gomuseum_app/features/content/data/models/museum_detail_model.dart';
import 'package:gomuseum_app/features/content/data/models/museum_summary_model.dart';
import 'package:gomuseum_app/features/content/data/models/object_content_model.dart';
import 'package:gomuseum_app/features/settings/presentation/providers/language_provider.dart';

final catalogDataSourceProvider = Provider<CatalogRemoteDataSource>((ref) {
  return CatalogRemoteDataSourceImpl(dio: ref.watch(dioProvider));
});

/// 缓存键必须含语言:此前只按 slug 做键、却在内部读 languageProvider,
/// 于是换语言→失效重取,**切回原来的语言→再次重取**,永远不命中缓存
/// (真机反馈:"切换回我原来选择过的语言又需要重新加载")。
/// 对照:objectListProvider 本来就按 (slug, category, language) 做键,没这问题。
///
/// ⚠️ **只缓存成功结果**——`autoDispose` + 成功后才 `keepAlive`。
/// 不带 autoDispose 的 family 会把 state 永久钉在 App 生命周期上,**错误态也一样**:
/// 一次瞬时网络抖动 → 这个 (馆,语言) 的 AsyncError 被永久缓存 → 之后再进页面
/// 直接拿缓存的错误渲染、**连请求都不发**(标题回退成 slug、分类条消失),
/// 只有重启 App 能解。2026-09-22 真机实证:波兰语下小皇宫整页加载失败,
/// 14 天 nginx 日志里那个 (petit_palais, pl) 请求一次都没出现过;杀进程重开即好。
/// 与语言无关——任何 (馆,语言) 组合碰上一次抖动都会这样。
final museumDetailProvider = FutureProvider.autoDispose
    .family<MuseumDetail, ({String slug, String language})>((ref, a) async {
  final detail = await ref
      .watch(catalogDataSourceProvider)
      .getMuseumDetail(slug: a.slug, language: a.language);
  ref.keepAlive(); // 成功才驻留;抛异常时走不到这里 → 页面退出即释放,下次重试
  return detail;
});

final objectContentProvider =
    FutureProvider.family<ObjectContent, ({String slug, String qid})>((ref, a) {
  final lang = apiLanguage(ref.watch(resolvedLocaleProvider));
  return ref
      .watch(catalogDataSourceProvider)
      .getObjectContent(slug: a.slug, qid: a.qid, language: lang);
});

/// A1 GET /api/v1/museums → flat list of all museums.
final museumsListProvider = FutureProvider<List<MuseumSummary>>((ref) async {
  final dio = ref.watch(dioProvider);
  final r = await dio.get('/api/v1/museums');
  return (r.data as List?)
          ?.whereType<Map<String, dynamic>>()
          .map(MuseumSummary.fromJson)
          .toList() ??
      const [];
});
