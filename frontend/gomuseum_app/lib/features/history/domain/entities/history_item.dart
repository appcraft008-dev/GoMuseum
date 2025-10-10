import 'package:equatable/equatable.dart';

/// History item entity
class HistoryItem extends Equatable {
  final String id;
  final String artworkName;
  final String artist;
  final String period;
  final String description;
  final double confidence;
  final DateTime timestamp;

  const HistoryItem({
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
}
