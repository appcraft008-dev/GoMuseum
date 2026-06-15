/// 馆包数据模型与 Provider（GET /api/v1/museums/{slug}）
library;

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:gomuseum_app/features/recognition/presentation/providers/recognition_providers.dart';

class MuseumPackArtwork {
  const MuseumPackArtwork({
    required this.qid,
    required this.titleZh,
    required this.artistZh,
    required this.periodZh,
    this.year,
    this.image,
    this.popularity = 0,
  });

  final String qid;
  final String titleZh;
  final String artistZh;
  final String periodZh;
  final String? year;
  final String? image;
  final int popularity;

  /// Wikimedia Commons 缩略图（Special:FilePath 支持 width 参数）
  String? thumb([int width = 400]) =>
      image == null ? null : '$image?width=$width';

  factory MuseumPackArtwork.fromJson(Map<String, dynamic> json) {
    return MuseumPackArtwork(
      qid: json['qid'] as String,
      titleZh: json['title_zh'] as String,
      artistZh: json['artist_zh'] as String? ?? '佚名',
      periodZh: json['period_zh'] as String? ?? '19世纪',
      year: json['year'] as String?,
      image: json['image'] as String?,
      popularity: json['popularity'] as int? ?? 0,
    );
  }
}

class MuseumPack {
  const MuseumPack({
    required this.slug,
    required this.nameZh,
    required this.cityZh,
    required this.artworkCount,
    required this.artworks,
  });

  final String slug;
  final String nameZh;
  final String cityZh;
  final int artworkCount;
  final List<MuseumPackArtwork> artworks;

  factory MuseumPack.fromJson(Map<String, dynamic> json) {
    return MuseumPack(
      slug: json['slug'] as String,
      nameZh: json['name_zh'] as String,
      cityZh: json['city_zh'] as String? ?? '',
      artworkCount: json['artwork_count'] as int? ?? 0,
      artworks: (json['artworks'] as List<dynamic>? ?? [])
          .map((e) => MuseumPackArtwork.fromJson(e as Map<String, dynamic>))
          .toList(),
    );
  }
}

/// 按 slug 拉取馆包（自动缓存于 provider 生命周期内）
final museumPackProvider =
    FutureProvider.family<MuseumPack, String>((ref, slug) async {
  final dio = ref.watch(dioProvider);
  final response = await dio.get('/api/v1/museums/$slug');
  return MuseumPack.fromJson(response.data as Map<String, dynamic>);
});
