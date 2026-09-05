import 'package:equatable/equatable.dart';

/// 一条足迹（一次识别）。
///
/// [museumSlug] + [qid] 是**点进去能看到真讲解**的入场券：`GuideArgs` 有两条路，
/// 只带 [HistoryItem] 拼出来的 `result` 走的是"刚拍完照"那条，讲解正文并不在
/// 足迹数据里。带上馆和 qid 才能走馆藏那条，拿到完整讲解。
/// 两者可空——老后端不返回这两个字段（加法契约）。
class HistoryItem extends Equatable {
  final String id;
  final String artworkName;
  final String artist;
  final String period;
  final String description;
  final double confidence;
  final DateTime timestamp;
  final String? museumSlug;
  final String? qid;
  final String? thumbnail;

  const HistoryItem({
    required this.id,
    required this.artworkName,
    required this.artist,
    required this.period,
    required this.description,
    required this.confidence,
    required this.timestamp,
    this.museumSlug,
    this.qid,
    this.thumbnail,
  });

  /// 能不能走"馆藏 + qid"那条路拿到完整讲解。
  bool get hasGuide => museumSlug != null && qid != null;

  @override
  List<Object?> get props => [
        id,
        artworkName,
        artist,
        period,
        description,
        confidence,
        timestamp,
        museumSlug,
        qid,
        thumbnail,
      ];
}
