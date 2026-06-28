// lib/features/content/data/models/museum_summary_model.dart
// A1 GET /api/v1/museums → [{slug, name_zh, name_en, city_zh, city_en, country, ...}]
// 后端同时返回中英两套名；前端按当前 UI 语言挑。
import 'package:equatable/equatable.dart';

class MuseumSummary extends Equatable {
  const MuseumSummary({
    required this.slug,
    required this.name,
    required this.nameEn,
    required this.city,
    required this.cityEn,
    required this.country,
    required this.coordinates,
    required this.artworkCount,
  });

  final String slug;

  /// 中文名（兼容旧字段：name → name_zh → slug）。
  final String name;

  /// 英文/拉丁名（name_en → name_zh → slug）。
  final String nameEn;

  /// 中文城市名。
  final String city;

  /// 英文/拉丁城市名（city_en → city_zh）。
  final String cityEn;

  final String country;

  /// [lat, lng]，A1 缺字段时为空列表。
  final List<double> coordinates;

  /// 藏品数，缺则 0。
  final int artworkCount;

  /// 按 UI 语言取馆名：zh→中文名；其余（en/fr…）→英文/拉丁名。
  String localizedName(String lang) => lang == 'zh' ? name : nameEn;

  /// 按 UI 语言取城市名。
  String localizedCity(String lang) => lang == 'zh' ? city : cityEn;

  factory MuseumSummary.fromJson(Map<String, dynamic> j) {
    final slug = j['slug'] as String? ?? '';
    final nameZh = j['name'] as String? ?? j['name_zh'] as String? ?? slug;
    final cityZh = j['city'] as String? ?? j['city_zh'] as String? ?? '';
    return MuseumSummary(
      slug: slug,
      name: nameZh,
      nameEn: j['name_en'] as String? ?? nameZh,
      city: cityZh,
      cityEn: j['city_en'] as String? ?? cityZh,
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
      [slug, name, nameEn, city, cityEn, country, coordinates, artworkCount];
}
