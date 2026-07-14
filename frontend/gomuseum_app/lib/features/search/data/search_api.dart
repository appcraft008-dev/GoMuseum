/// 搜索数据层：全局 GET /api/v1/search 与馆域 GET /api/v1/museums/{slug}/search。
///
/// 稳定契约 + 可替换引擎：前端只认契约字段，后端引擎（进程内→Meilisearch）可换、前端不动。
/// 契约容错：museum/thumbnail 用 as String?，has_image 用 as bool? ?? false（禁裸强转）。
library;

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:gomuseum_app/features/recognition/presentation/providers/recognition_providers.dart';

/// 藏品命中行（无图 stub 照常在结果里，has_image=false）。
class SearchObject {
  const SearchObject({
    required this.qid,
    required this.title,
    required this.artist,
    this.year,
    this.thumbnail,
    this.museum,
    this.hasImage = false,
  });

  final String qid;
  final String title;
  final String artist;
  final String? year;
  final String? thumbnail;

  /// 归属馆 slug（点击跳讲解页用，与识别 match 同款导航）。
  final String? museum;
  final bool hasImage;

  factory SearchObject.fromJson(Map<String, dynamic> j) => SearchObject(
        qid: j['qid'] as String? ?? '',
        title: j['title'] as String? ?? (j['qid'] as String? ?? ''),
        artist: j['artist'] as String? ?? '',
        year: j['year'] as String?,
        thumbnail: j['thumbnail'] as String?,
        museum: j['museum'] as String?,
        hasImage: j['has_image'] as bool? ?? false,
      );
}

/// 博物馆命中（仅全局端点返回）。
class SearchMuseumHit {
  const SearchMuseumHit(
      {required this.slug, required this.name, required this.city});

  final String slug;
  final String name;
  final String city;

  factory SearchMuseumHit.fromJson(Map<String, dynamic> j) => SearchMuseumHit(
        slug: j['slug'] as String? ?? '',
        name: j['name'] as String? ?? (j['slug'] as String? ?? ''),
        city: j['city'] as String? ?? '',
      );
}

class SearchResults {
  const SearchResults({this.museums = const [], this.objects = const []});

  final List<SearchMuseumHit> museums;
  final List<SearchObject> objects;

  bool get isEmpty => museums.isEmpty && objects.isEmpty;

  static const empty = SearchResults();

  factory SearchResults.fromJson(Map<String, dynamic> j) => SearchResults(
        museums: (j['museums'] as List<dynamic>? ?? [])
            .map((e) => SearchMuseumHit.fromJson(e as Map<String, dynamic>))
            .toList(),
        objects: (j['objects'] as List<dynamic>? ?? [])
            .map((e) => SearchObject.fromJson(e as Map<String, dynamic>))
            .toList(),
      );
}

/// 搜索请求键：slug=null → 全局（含 museums 段）；slug 给定 → 馆域（仅 objects）。
/// record 值相等 → provider 天然按 (slug,q,lang) 缓存。
typedef SearchQuery = ({String? slug, String q, String lang});

/// 空 query → 直接返回空（不打网络，诚实空态）。
final searchProvider =
    FutureProvider.family<SearchResults, SearchQuery>((ref, key) async {
  final q = key.q.trim();
  if (q.isEmpty) return SearchResults.empty;
  final dio = ref.watch(dioProvider);
  final path = key.slug == null
      ? '/api/v1/search'
      : '/api/v1/museums/${key.slug}/search';
  final resp =
      await dio.get(path, queryParameters: {'q': q, 'language': key.lang});
  return SearchResults.fromJson(resp.data as Map<String, dynamic>);
});
