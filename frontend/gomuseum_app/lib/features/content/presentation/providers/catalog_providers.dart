// lib/features/content/presentation/providers/catalog_providers.dart
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:gomuseum_app/features/auth/presentation/auth_provider.dart';
import 'package:gomuseum_app/features/content/data/datasources/catalog_remote_datasource.dart';
import 'package:gomuseum_app/features/content/data/models/museum_detail_model.dart';
import 'package:gomuseum_app/features/content/data/models/museum_summary_model.dart';
import 'package:gomuseum_app/features/content/data/models/object_content_model.dart';

final catalogDataSourceProvider = Provider<CatalogRemoteDataSource>((ref) {
  return CatalogRemoteDataSourceImpl(dio: ref.watch(dioProvider));
});

final museumDetailProvider =
    FutureProvider.family<MuseumDetail, String>((ref, slug) {
  return ref.watch(catalogDataSourceProvider).getMuseumDetail(slug: slug);
});

final objectContentProvider =
    FutureProvider.family<ObjectContent, ({String slug, String qid})>((ref, a) {
  return ref
      .watch(catalogDataSourceProvider)
      .getObjectContent(slug: a.slug, qid: a.qid);
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
