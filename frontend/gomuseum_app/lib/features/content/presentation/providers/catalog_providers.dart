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
final museumDetailProvider =
    FutureProvider.family<MuseumDetail, ({String slug, String language})>(
        (ref, a) {
  return ref
      .watch(catalogDataSourceProvider)
      .getMuseumDetail(slug: a.slug, language: a.language);
});

final objectContentProvider =
    FutureProvider.family<ObjectContent, ({String slug, String qid})>((ref, a) {
  final lang = apiLanguage(ref.watch(languageProvider));
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
