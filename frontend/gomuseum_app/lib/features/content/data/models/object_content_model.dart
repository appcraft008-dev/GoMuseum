// lib/features/content/data/models/object_content_model.dart
import 'package:equatable/equatable.dart';
import 'package:gomuseum_app/features/content/data/models/object_list_model.dart';

/// A5 status: absent|generating|published|needs_review → 收敛到 ContentStatus。
ContentStatus _statusFromA5(String? s) {
  switch (s) {
    case 'generating':
      return ContentStatus.generating;
    case 'absent':
      return ContentStatus.stub;
    case 'published':
    case 'needs_review':
      return ContentStatus.ready;
    default:
      return ContentStatus.ready;
  }
}

class ObjectImage extends Equatable {
  const ObjectImage({required this.url, required this.credit});
  final String url;
  final String? credit;
  factory ObjectImage.fromJson(Map<String, dynamic> j) => ObjectImage(
      url: j['url'] as String? ?? '', credit: j['credit'] as String?);
  @override
  List<Object?> get props => [url, credit];
}

class ObjectFacts extends Equatable {
  const ObjectFacts({
    this.artist,
    this.date,
    this.medium,
    this.dimensions,
    this.inventory,
    this.location,
    this.provenance,
    this.artistLife,
    this.exhibitions = const [],
    this.bibliography = const [],
  });
  final String? artist,
      date,
      medium,
      dimensions,
      inventory,
      location,
      provenance,
      artistLife;
  final List<String> exhibitions, bibliography;

  factory ObjectFacts.fromJson(Map<String, dynamic>? j) {
    final m = j ?? const {};
    List<String> strList(dynamic v) =>
        (v as List?)
            ?.map((e) => e?.toString() ?? '')
            .where((s) => s.isNotEmpty)
            .toList() ??
        const [];
    return ObjectFacts(
      artist: m['artist'] as String?,
      date: m['date'] as String?,
      medium: m['medium'] as String?,
      dimensions: m['dimensions'] as String?,
      inventory: m['inventory'] as String?,
      location: m['location'] as String?,
      provenance: m['provenance'] as String?,
      artistLife: m['artist_life'] as String?,
      exhibitions: strList(m['exhibitions']),
      bibliography: strList(m['bibliography']),
    );
  }
  @override
  List<Object?> get props => [
        artist,
        date,
        medium,
        dimensions,
        inventory,
        location,
        provenance,
        artistLife,
        exhibitions,
        bibliography
      ];
}

class ObjectTab extends Equatable {
  const ObjectTab({
    required this.sectionCode,
    required this.label,
    required this.body,
    required this.audioUrl,
  });
  final String sectionCode;
  final String label;
  final String? body;
  final String? audioUrl;

  /// body 空/缺 → 前端显「待完善」。
  bool get hasBody => (body ?? '').trim().isNotEmpty;

  factory ObjectTab.fromJson(Map<String, dynamic> j) => ObjectTab(
        sectionCode: j['section_code'] as String? ?? '',
        label: j['label'] as String? ?? '段落',
        body: j['body'] as String?,
        audioUrl: j['audio_url'] as String?,
      );
  @override
  List<Object?> get props => [sectionCode, label, body, audioUrl];
}

class SuggestedQuestion extends Equatable {
  const SuggestedQuestion({required this.question, required this.answer});
  final String question;
  final String? answer;
  factory SuggestedQuestion.fromJson(Map<String, dynamic> j) =>
      SuggestedQuestion(
        question: j['question'] as String? ?? '',
        answer: j['answer'] as String?,
      );
  @override
  List<Object?> get props => [question, answer];
}

class DefaultGuide extends Equatable {
  const DefaultGuide({required this.body, required this.audioUrl});
  final String body;
  final String? audioUrl;

  bool get hasBody => body.trim().isNotEmpty;

  factory DefaultGuide.fromJson(Map<String, dynamic> j) => DefaultGuide(
        // 禁裸 as String：富化字段天然可缺，统一可空 + 回退
        body: j['body'] is String ? j['body'] as String : '',
        audioUrl: j['audio_url'] is String ? j['audio_url'] as String : null,
      );

  @override
  List<Object?> get props => [body, audioUrl];
}

/// 作者卡（必选常驻；区别于 tabs 的动态隐藏）。
/// name 一定有；其余字段可空/为空，缺啥不显啥。
class Artist extends Equatable {
  const Artist({
    required this.name,
    this.birth,
    this.death,
    this.nationality,
    this.bio,
    this.notableWorks = const [],
  });

  final String name;
  final String? birth, death, nationality, bio;
  final List<String> notableWorks;

  factory Artist.fromJson(Map<String, dynamic> j) {
    String? str(dynamic v) => v is String && v.isNotEmpty ? v : null;
    return Artist(
      name: j['name'] is String ? j['name'] as String : '',
      birth: str(j['birth']),
      death: str(j['death']),
      nationality: str(j['nationality']),
      bio: str(j['bio']),
      notableWorks: (j['notable_works'] as List?)
              ?.map((e) => e?.toString() ?? '')
              .where((s) => s.isNotEmpty)
              .toList() ??
          const [],
    );
  }

  @override
  List<Object?> get props =>
      [name, birth, death, nationality, bio, notableWorks];
}

class ObjectContent extends Equatable {
  const ObjectContent({
    required this.qid,
    required this.category,
    required this.language,
    required this.status,
    required this.title,
    required this.images,
    required this.facts,
    required this.tabs,
    required this.suggestedQuestions,
    this.generating = false,
    this.defaultGuide,
    this.artist,
  });
  final String qid;
  final String category;
  final String language;
  final ContentStatus status;

  /// 后端任务锁信号：true = 正在懒生成/懒翻译（加法字段，老后端缺 → false）。
  final bool generating;
  final String title;
  final List<ObjectImage> images;
  final ObjectFacts facts;
  final List<ObjectTab> tabs;
  final List<SuggestedQuestion> suggestedQuestions;
  final DefaultGuide? defaultGuide;
  final Artist? artist;

  factory ObjectContent.fromJson(Map<String, dynamic> j) => ObjectContent(
        qid: j['qid'] as String? ?? '',
        category: j['category'] as String? ?? '',
        language: j['language'] as String? ?? 'zh',
        status: _statusFromA5(j['status'] as String?),
        generating: j['generating'] as bool? ?? false,
        title: j['title'] as String? ?? '未命名',
        images: (j['images'] as List?)
                ?.whereType<Map<String, dynamic>>()
                .map(ObjectImage.fromJson)
                .where((i) => i.url.isNotEmpty)
                .toList() ??
            const [],
        facts: ObjectFacts.fromJson(j['facts'] as Map<String, dynamic>?),
        tabs: (j['tabs'] as List?)
                ?.whereType<Map<String, dynamic>>()
                .map(ObjectTab.fromJson)
                .toList() ??
            const [],
        suggestedQuestions: (j['suggested_questions'] as List?)
                ?.whereType<Map<String, dynamic>>()
                .map(SuggestedQuestion.fromJson)
                .where((q) => q.question.isNotEmpty)
                .toList() ??
            const [],
        defaultGuide: j['default_guide'] is Map<String, dynamic>
            ? DefaultGuide.fromJson(j['default_guide'] as Map<String, dynamic>)
            : null,
        artist: j['artist'] is Map<String, dynamic>
            ? Artist.fromJson(j['artist'] as Map<String, dynamic>)
            : null,
      );

  @override
  List<Object?> get props => [
        qid,
        category,
        language,
        status,
        generating,
        title,
        images,
        facts,
        tabs,
        suggestedQuestions,
        defaultGuide,
        artist
      ];
}
