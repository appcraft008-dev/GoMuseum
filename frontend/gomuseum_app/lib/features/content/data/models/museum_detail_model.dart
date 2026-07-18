// lib/features/content/data/models/museum_detail_model.dart
import 'package:equatable/equatable.dart';

class MuseumCategory extends Equatable {
  const MuseumCategory(
      {required this.code, required this.label, required this.count});
  final String code;
  final String label;
  final int count;

  factory MuseumCategory.fromJson(Map<String, dynamic> j) => MuseumCategory(
        code: j['code'] as String? ?? '',
        label: j['label'] as String? ?? (j['code'] as String? ?? '未分类'),
        count: (j['count'] as num?)?.toInt() ?? 0,
      );

  @override
  List<Object?> get props => [code, label, count];
}

class MuseumDetail extends Equatable {
  const MuseumDetail({
    required this.slug,
    required this.name,
    required this.nameEn,
    required this.city,
    required this.country,
    required this.coordinates,
    required this.openingHours,
    required this.officialUrl,
    required this.categories,
    this.catalogCount,
    this.archiveCount,
    this.description,
    this.coverImage,
  });

  final String slug;

  /// 中文名（name → name_zh → slug）。
  final String name;

  /// 英文/拉丁名（name_en → name_zh → slug）。
  final String nameEn;
  final String city;
  final String country;
  final List<double> coordinates; // [lat, lng]，缺则空
  final String? openingHours;
  final String? officialUrl;
  final List<MuseumCategory> categories;

  /// 在线图录条数（可识别/搜索）；老后端无此字段 → null，不显示双数字行。
  final int? catalogCount;

  /// 档案条目条数；老后端无此字段 → null。
  final int? archiveCount;

  /// 馆叙事介绍（按 language，加法字段）；缺/生成失败 → null，介绍卡整体隐藏。
  final String? description;

  /// 封面直链（large 档，加法字段）；无合规封面 → null，封面 banner 隐藏。
  final String? coverImage;

  /// 按 UI 语言取馆名：zh→中文名；其余→英文/拉丁名。
  String localizedName(String lang) => lang == 'zh' ? name : nameEn;

  factory MuseumDetail.fromJson(Map<String, dynamic> j) {
    final slug = j['slug'] as String? ?? '';
    final nameZh = j['name'] as String? ?? j['name_zh'] as String? ?? slug;
    return MuseumDetail(
      slug: slug,
      name: nameZh,
      nameEn: j['name_en'] as String? ?? nameZh,
      city: j['city'] as String? ?? j['city_zh'] as String? ?? '',
      country: j['country'] as String? ?? '',
      coordinates: (j['coordinates'] as List?)
              ?.map((e) => (e as num?)?.toDouble() ?? 0)
              .toList() ??
          const [],
      openingHours: j['opening_hours'] as String?,
      officialUrl: j['official_url'] as String?,
      categories: (j['categories'] as List?)
              ?.whereType<Map<String, dynamic>>()
              .map(MuseumCategory.fromJson)
              .toList() ??
          const [],
      catalogCount: (j['catalog_count'] as num?)?.toInt(),
      archiveCount: (j['archive_count'] as num?)?.toInt(),
      // 加法字段：空串视同缺失（隐藏，不显空块）。
      description: (j['description'] as String?)?.trim().isNotEmpty == true
          ? (j['description'] as String).trim()
          : null,
      coverImage: (j['cover_image'] as String?)?.isNotEmpty == true
          ? j['cover_image'] as String
          : null,
    );
  }

  @override
  List<Object?> get props => [
        slug,
        name,
        nameEn,
        city,
        country,
        coordinates,
        openingHours,
        officialUrl,
        categories,
        catalogCount,
        archiveCount,
        description,
        coverImage,
      ];
}
