import '../../domain/entities/history_item.dart';

/// History item model (data layer)
class HistoryItemModel extends HistoryItem {
  const HistoryItemModel({
    required super.id,
    required super.artworkName,
    required super.artist,
    required super.period,
    required super.description,
    required super.confidence,
    required super.timestamp,
    super.museumSlug,
    super.qid,
    super.thumbnail,
  });

  /// Create model from JSON
  ///
  /// ⚠️ **禁止裸 `as String`**（项目硬约束，见 CLAUDE.md「数据契约容错」）。
  /// 这里原本是 `json['artist'] as String`——富化数据天然缺字段，一个 null
  /// 就让整个足迹页崩掉，正是 2026-06-16 `title_zh` 变 null 那次事故的形态。
  /// 后端这侧也给了回退（见 history.py 纪律 2），两边都做，不互相指望。
  factory HistoryItemModel.fromJson(Map<String, dynamic> json) {
    return HistoryItemModel(
      id: json['id'] as String? ?? '',
      artworkName: json['artwork_name'] as String? ?? '',
      artist: json['artist'] as String? ?? '',
      period: json['period'] as String? ?? '',
      description: json['description'] as String? ?? '',
      confidence: (json['confidence'] as num?)?.toDouble() ?? 0.0,
      timestamp: DateTime.tryParse(json['timestamp'] as String? ?? '') ??
          DateTime.now(),
      museumSlug: json['museum_slug'] as String?,
      qid: json['qid'] as String?,
      thumbnail: json['thumbnail'] as String?,
    );
  }

  /// Convert model to JSON
  Map<String, dynamic> toJson() {
    return {
      'id': id,
      'artwork_name': artworkName,
      'artist': artist,
      'period': period,
      'description': description,
      'confidence': confidence,
      'timestamp': timestamp.toIso8601String(),
      'museum_slug': museumSlug,
      'qid': qid,
      'thumbnail': thumbnail,
    };
  }

  /// Convert to entity
  HistoryItem toEntity() {
    return HistoryItem(
      id: id,
      artworkName: artworkName,
      artist: artist,
      period: period,
      description: description,
      confidence: confidence,
      timestamp: timestamp,
      museumSlug: museumSlug,
      qid: qid,
      thumbnail: thumbnail,
    );
  }
}
