/// 新识别端点 `POST /museums/{slug}/recognize` 的响应模型。
///
/// 接地识别：不返回自由文本猜测，只给 outcome + 已收录藏品的 qid/本地化标题。
/// 契约容错：禁裸 `as String`，可缺字段一律可空 + 回退。
library;

import 'package:equatable/equatable.dart';

enum RecognizeOutcome { match, candidates, unrecognized }

RecognizeOutcome _outcomeFrom(String? s) {
  switch (s) {
    case 'match':
      return RecognizeOutcome.match;
    case 'candidates':
      return RecognizeOutcome.candidates;
    default:
      return RecognizeOutcome.unrecognized;
  }
}

/// 命中/候选共用的藏品引用（title/artist 已按 language 本地化）。
class RecognizedItem extends Equatable {
  const RecognizedItem({
    required this.qid,
    required this.title,
    required this.artist,
    required this.thumbnail,
    required this.score,
    this.museum,
    this.image,
    this.credit,
  });

  final String qid;
  final String title;
  final String artist;
  final String? thumbnail;

  /// match 用 confidence、candidates 用 score，统一到此。
  final double score;

  /// 归属馆 slug（全局识别端点返回；后端 museum_id 非空）。缺了就判无效（见 isValid）
  /// —— 原先回落写死的 'orsay'，跨城后等于把人带进错的馆。
  final String? museum;

  /// 候选全屏比对用的大图(S3 加法字段;老后端/老缓存没有 → 回落 thumbnail)。
  final String? image;

  /// 图片署名(CC 协议要求;作者本人已由后端剔除)。
  final String? credit;

  factory RecognizedItem.fromJson(Map<String, dynamic> j) {
    final rawScore = j['confidence'] ?? j['score'];
    final thumb = j['thumbnail'] as String?;
    return RecognizedItem(
      qid: j['qid'] as String? ?? '',
      title: j['title'] as String? ?? '',
      artist: j['artist'] as String? ?? '',
      thumbnail: thumb,
      image: j['image'] as String? ?? thumb,
      credit: j['credit'] as String?,
      score: rawScore is num ? rawScore.toDouble() : 0.0,
      museum: j['museum'] as String?,
    );
  }

  bool get isValid => qid.isNotEmpty && (museum?.isNotEmpty ?? false);

  @override
  List<Object?> get props =>
      [qid, title, artist, thumbnail, score, museum, image, credit];
}

class RecognizeResponse extends Equatable {
  const RecognizeResponse({
    required this.outcome,
    required this.match,
    required this.candidates,
    required this.labelText,
    required this.reason,
    this.phash,
    this.photoFeedback = false,
  });

  final RecognizeOutcome outcome;
  final RecognizedItem? match;
  final List<RecognizedItem> candidates;
  final String? labelText;
  final String? reason;

  /// 本次照片的感知哈希；确认卡点选时回传后端做 CLIP 校准。老后端无此字段 → null。
  final String? phash;

  /// S5 服务端开关:true 才弹「把这张照片发给我们?」(隐私政策上线前后端恒给 false)。
  final bool photoFeedback;

  factory RecognizeResponse.fromJson(Map<String, dynamic> j) {
    final matchJson = j['match'];
    return RecognizeResponse(
      outcome: _outcomeFrom(j['outcome'] as String?),
      match: matchJson is Map<String, dynamic>
          ? RecognizedItem.fromJson(matchJson)
          : null,
      candidates: (j['candidates'] as List?)
              ?.whereType<Map<String, dynamic>>()
              .map(RecognizedItem.fromJson)
              .where((c) => c.isValid)
              .toList() ??
          const [],
      labelText: (j['label_text'] as String?)?.trim().isNotEmpty == true
          ? (j['label_text'] as String).trim()
          : null,
      reason: j['reason'] as String?,
      phash: j['phash'] as String?,
      photoFeedback: j['photo_feedback'] as bool? ?? false,
    );
  }

  @override
  List<Object?> get props =>
      [outcome, match, candidates, labelText, reason, phash, photoFeedback];
}
