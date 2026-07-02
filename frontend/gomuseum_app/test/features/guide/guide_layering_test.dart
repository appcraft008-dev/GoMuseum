import 'package:flutter_test/flutter_test.dart';
import 'package:gomuseum_app/features/content/data/models/object_content_model.dart';
import 'package:gomuseum_app/features/content/data/models/object_list_model.dart';
import 'package:gomuseum_app/features/guide/presentation/logic/guide_layering.dart';

ObjectTab tab(String code, {String? body, String? audio}) =>
    ObjectTab(sectionCode: code, label: code, body: body, audioUrl: audio);

ObjectContent content({
  DefaultGuide? guide,
  List<ObjectTab> tabs = const [],
}) =>
    ObjectContent(
      qid: 'Q',
      category: '',
      language: 'zh',
      status: ContentStatus.ready,
      title: 'T',
      images: const [],
      facts: const ObjectFacts(),
      tabs: tabs,
      suggestedQuestions: const [],
      defaultGuide: guide,
    );

void main() {
  test('无 default_guide → overview 提升为主角，抽屉为其余 tab', () {
    final c = content(tabs: [
      tab('overview', body: '通用正文'),
      tab('artist', body: '作者'),
      tab('analysis', body: '分析'),
    ]);
    final l = GuideLayering.from(c);
    expect(l.heroBody, '通用正文');
    expect(l.heroAudioUrl, isNull);
    expect(l.deepTabs.map((t) => t.sectionCode), ['artist', 'analysis']);
    expect(l.deepCount, 2);
  });

  test('有 default_guide → 主角用它，overview 从抽屉移除（隐藏通用）', () {
    final c = content(
      guide: const DefaultGuide(body: 'DG 正文', audioUrl: 'http://a.mp3'),
      tabs: [tab('overview', body: '通用正文'), tab('artist', body: '作者')],
    );
    final l = GuideLayering.from(c);
    expect(l.heroBody, 'DG 正文');
    expect(l.heroAudioUrl, 'http://a.mp3');
    expect(l.deepTabs.map((t) => t.sectionCode), ['artist']);
  });

  test('无 overview、无 default_guide → 首个有正文 tab 当主角，其余进抽屉', () {
    final c = content(tabs: [
      tab('artist', body: '作者'),
      tab('analysis', body: '分析'),
    ]);
    final l = GuideLayering.from(c);
    expect(l.heroBody, '作者');
    expect(l.deepTabs.map((t) => t.sectionCode), ['analysis']);
  });

  test('overview body 为空 → 跳过它选首个有正文 tab 当主角', () {
    final c = content(tabs: [
      tab('overview', body: '   '),
      tab('artist', body: '作者'),
    ]);
    final l = GuideLayering.from(c);
    expect(l.heroBody, '作者');
    // 被提升的是 artist，overview 仍留抽屉
    expect(l.deepTabs.map((t) => t.sectionCode), ['overview']);
  });

  test('default_guide 在场 + 无 overview tab → 全部 tab 进抽屉(不误删)', () {
    // 对齐 staging 现状：default_guide 上线后 tabs=[background,analysis,...]，
    // 不应把首个有正文 tab 当 promoted 误删。
    final c = content(
      guide: const DefaultGuide(body: '主线讲解', audioUrl: null),
      tabs: [
        tab('background', body: '背景'),
        tab('analysis', body: '分析'),
        tab('significance', body: '意义'),
      ],
    );
    final l = GuideLayering.from(c);
    expect(l.heroBody, '主线讲解');
    expect(l.deepTabs.map((t) => t.sectionCode),
        ['background', 'analysis', 'significance']);
    expect(l.deepCount, 3);
  });

  test('完全无内容 → heroBody 空、deepTabs 空、hasDeep=false', () {
    final l = GuideLayering.from(content(tabs: const []));
    expect(l.heroBody, '');
    expect(l.deepTabs, isEmpty);
    expect(l.hasDeep, isFalse);
  });
}
