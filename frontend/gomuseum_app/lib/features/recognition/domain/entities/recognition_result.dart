import 'package:equatable/equatable.dart';

/// 识别结果实体(纯业务对象,无依赖)
class RecognitionResult extends Equatable {
  final String id;
  final String artworkName;
  final String artist;
  final String period;
  final String description;
  final double confidence;
  final DateTime timestamp;

  const RecognitionResult({
    required this.id,
    required this.artworkName,
    required this.artist,
    required this.period,
    required this.description,
    required this.confidence,
    required this.timestamp,
  });

  @override
  List<Object?> get props => [
        id,
        artworkName,
        artist,
        period,
        description,
        confidence,
        timestamp,
      ];

  @override
  String toString() {
    return 'RecognitionResult(id: $id, artworkName: $artworkName, artist: $artist, '
        'period: $period, confidence: $confidence, timestamp: $timestamp)';
  }
}
