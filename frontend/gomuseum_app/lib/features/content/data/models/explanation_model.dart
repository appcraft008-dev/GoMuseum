import 'package:gomuseum_app/features/content/domain/entities/explanation.dart';

/// Explanation的数据模型(带JSON序列化)
class ExplanationModel extends Explanation {
  const ExplanationModel({
    required super.title,
    required super.summary,
    required super.historicalContext,
    required super.artisticAnalysis,
    required super.culturalSignificance,
    required super.interestingFacts,
    required super.language,
  });

  /// 从JSON创建
  factory ExplanationModel.fromJson(Map<String, dynamic> json) {
    return ExplanationModel(
      title: json['title'] as String,
      summary: json['summary'] as String,
      historicalContext: json['historical_context'] as String,
      artisticAnalysis: json['artistic_analysis'] as String,
      culturalSignificance: json['cultural_significance'] as String,
      interestingFacts: (json['interesting_facts'] as List<dynamic>)
          .map((e) => e as String)
          .toList(),
      language: json['language'] as String,
    );
  }

  /// 转换为JSON
  Map<String, dynamic> toJson() {
    return {
      'title': title,
      'summary': summary,
      'historical_context': historicalContext,
      'artistic_analysis': artisticAnalysis,
      'cultural_significance': culturalSignificance,
      'interesting_facts': interestingFacts,
      'language': language,
    };
  }

  /// 从Entity创建Model
  factory ExplanationModel.fromEntity(Explanation entity) {
    return ExplanationModel(
      title: entity.title,
      summary: entity.summary,
      historicalContext: entity.historicalContext,
      artisticAnalysis: entity.artisticAnalysis,
      culturalSignificance: entity.culturalSignificance,
      interestingFacts: entity.interestingFacts,
      language: entity.language,
    );
  }
}
