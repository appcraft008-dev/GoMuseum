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
  });

  /// Create model from JSON
  factory HistoryItemModel.fromJson(Map<String, dynamic> json) {
    return HistoryItemModel(
      id: json['id'] as String,
      artworkName: json['artwork_name'] as String,
      artist: json['artist'] as String,
      period: json['period'] as String,
      description: json['description'] as String,
      confidence: (json['confidence'] as num).toDouble(),
      timestamp: DateTime.parse(json['timestamp'] as String),
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
    );
  }
}
