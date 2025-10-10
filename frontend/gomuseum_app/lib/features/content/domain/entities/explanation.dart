import 'package:equatable/equatable.dart';

/// 艺术品讲解实体(纯业务对象,无依赖)
class Explanation extends Equatable {
  final String title;
  final String summary;
  final String historicalContext;
  final String artisticAnalysis;
  final String culturalSignificance;
  final List<String> interestingFacts;
  final String language;

  const Explanation({
    required this.title,
    required this.summary,
    required this.historicalContext,
    required this.artisticAnalysis,
    required this.culturalSignificance,
    required this.interestingFacts,
    required this.language,
  });

  @override
  List<Object?> get props => [
        title,
        summary,
        historicalContext,
        artisticAnalysis,
        culturalSignificance,
        interestingFacts,
        language,
      ];

  @override
  String toString() {
    return 'Explanation(title: $title, language: $language, facts: ${interestingFacts.length})';
  }
}
