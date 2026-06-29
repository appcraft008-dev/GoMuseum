import 'package:gomuseum_app/features/content/data/models/object_content_model.dart';

/// 讲解页「分层导览」派生逻辑（无 Flutter 依赖，纯函数，便于单测）。
///
/// 规则（详见 spec 2026-06-29-guide-page-layered-redesign-design）：
/// - 主角 body = default_guide.body ?? 被提升 tab.body
/// - 被提升 tab：优先 section_code=='overview' 且有正文；否则首个有正文 tab
/// - 深度抽屉 = 全部 tab 去掉被提升的那个（default_guide 在场时也去掉 overview）
class GuideLayering {
  const GuideLayering({
    required this.heroBody,
    required this.heroAudioUrl,
    required this.deepTabs,
  });

  final String heroBody;
  final String? heroAudioUrl;
  final List<ObjectTab> deepTabs;

  int get deepCount => deepTabs.length;
  bool get hasDeep => deepTabs.isNotEmpty;
  bool get hasHero => heroBody.trim().isNotEmpty;

  static const String overviewCode = 'overview';

  factory GuideLayering.from(ObjectContent c) {
    final tabs = c.tabs;
    // 选被提升为主角的 tab：优先有正文的 overview，否则首个有正文 tab
    ObjectTab? promoted;
    for (final t in tabs) {
      if (t.sectionCode == overviewCode && t.hasBody) {
        promoted = t;
        break;
      }
    }
    promoted ??= tabs.where((t) => t.hasBody).cast<ObjectTab?>().firstWhere(
          (_) => true,
          orElse: () => null,
        );

    final guide = c.defaultGuide;
    final heroBody =
        (guide != null && guide.hasBody) ? guide.body : (promoted?.body ?? '');
    final heroAudio = (guide?.audioUrl != null && guide!.audioUrl!.isNotEmpty)
        ? guide.audioUrl
        : promoted?.audioUrl;

    // 抽屉：去掉被提升的 tab；default_guide 在场时额外去掉 overview。
    final deep = <ObjectTab>[];
    for (final t in tabs) {
      if (identical(t, promoted)) continue;
      if (guide != null && guide.hasBody && t.sectionCode == overviewCode) {
        continue;
      }
      deep.add(t);
    }

    return GuideLayering(
      heroBody: heroBody,
      heroAudioUrl: heroAudio,
      deepTabs: deep,
    );
  }
}
