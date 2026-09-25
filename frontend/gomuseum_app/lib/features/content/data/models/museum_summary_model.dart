// lib/features/content/data/models/museum_summary_model.dart
// A1 GET /api/v1/museums → [{slug, name_zh, name_en, city_zh, city_en, country, ...}]
// 后端同时返回中英两套名；前端按当前 UI 语言挑。
import 'package:equatable/equatable.dart';

/// 解析后端的 `name_i18n`（十语馆名，加法字段，2026-09-21）。
///
/// 老后端不返回这个键 → 空表，取名回退 name_zh/name_en，与改动前完全一致。
///
/// ⚠️ 整条路径不许出现裸强转（`as Map` / `as String`）：富化数据天然缺字段，
/// 而这个键将来也可能被中间层换形状。类型不对就当"没有"，一律走回退，
/// 绝不让馆名解析把页面整页拖崩（2026-06-16 事故就是这么来的）。
Map<String, String> parseNameI18n(dynamic raw) {
  if (raw is! Map) return const {};
  return {
    for (final e in raw.entries)
      if (e.value is String && (e.value as String).isNotEmpty)
        '${e.key}': e.value as String,
  };
}

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
    this.coverImage,
    this.nameI18n = const {},
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

  /// 探索页缩略图(thumb 档，加法字段，2026-07-20)；无合规封面 → null，前端显占位图标。
  final String? coverImage;

  /// 十语馆名（后端 `name_i18n`）。老后端不返回 → 空表。
  final Map<String, String> nameI18n;

  /// 按 UI 语言取馆名。
  ///
  /// ⚠️ 这里原本是 `lang == 'zh' ? name : nameEn` —— 非中文一律吃英文名，
  /// 法语用户看到的是 "Louvre Museum"。而橘园/奥赛/小皇宫的 name_en 恰好写成
  /// 法语拼写，所以现象是"只有卢浮宫没翻译"，掩盖了"十语只有两套名"这个真相。
  /// 回退链留着：后端老版本或 yaml 没配的馆仍按旧行为走。
  String localizedName(String lang) =>
      nameI18n[lang] ?? (lang == 'zh' ? name : nameEn);

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
      coverImage: (j['cover_image'] as String?)?.isNotEmpty == true
          ? j['cover_image'] as String
          : null,
      nameI18n: parseNameI18n(j['name_i18n']),
    );
  }

  @override
  List<Object?> get props => [
        slug,
        name,
        nameEn,
        city,
        cityEn,
        country,
        coordinates,
        artworkCount,
        coverImage,
        nameI18n
      ];
}
