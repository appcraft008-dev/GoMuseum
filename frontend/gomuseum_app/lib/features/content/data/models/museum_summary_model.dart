// lib/features/content/data/models/museum_summary_model.dart
// A1 GET /api/v1/museums → [{slug, name, city, country, coordinates, artwork_count}]
import 'package:equatable/equatable.dart';

class MuseumSummary extends Equatable {
  const MuseumSummary({
    required this.slug,
    required this.name,
    required this.city,
    required this.country,
    required this.coordinates,
    required this.artworkCount,
  });

  final String slug;
  final String name;
  final String city;
  final String country;

  /// [lat, lng]，A1 缺字段时为空列表。
  final List<double> coordinates;

  /// 藏品数，缺则 0。
  final int artworkCount;

  factory MuseumSummary.fromJson(Map<String, dynamic> j) {
    final slug = j['slug'] as String? ?? '';
    return MuseumSummary(
      slug: slug,
      // 加法兼容：新 name → 旧 name_zh → slug
      name: j['name'] as String? ?? j['name_zh'] as String? ?? slug,
      city: j['city'] as String? ?? j['city_zh'] as String? ?? '',
      country: j['country'] as String? ?? '',
      coordinates: (j['coordinates'] as List?)
              ?.map((e) => (e as num?)?.toDouble() ?? 0.0)
              .toList() ??
          const [],
      artworkCount: (j['artwork_count'] as num?)?.toInt() ?? 0,
    );
  }

  @override
  List<Object?> get props =>
      [slug, name, city, country, coordinates, artworkCount];
}
