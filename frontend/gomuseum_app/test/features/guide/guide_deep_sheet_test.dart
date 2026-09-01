import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gomuseum_app/features/content/data/models/object_content_model.dart';
import 'package:gomuseum_app/features/guide/presentation/widgets/guide_audio_player.dart';
import 'package:gomuseum_app/features/guide/presentation/widgets/guide_deep_sheet.dart';
import 'package:gomuseum_app/l10n/app_localizations.dart';
import 'package:gomuseum_app/theme/app_theme.dart';

void main() {
  testWidgets('抽屉渲染 tab 标签与首个 tab 正文，切换 tab 换正文', (t) async {
    final tabs = [
      const ObjectTab(
          sectionCode: 'artist', label: '作者', body: '作者正文', hasAudio: false),
      const ObjectTab(
          sectionCode: 'analysis', label: '分析', body: '分析正文', hasAudio: false),
    ];
    await t.pumpWidget(MaterialApp(
      localizationsDelegates: AppLocalizations.localizationsDelegates,
      supportedLocales: AppLocalizations.supportedLocales,
      locale: const Locale('zh'),
      theme: AppTheme.lightTheme(),
      home: Scaffold(body: GuideDeepSheetContent(tabs: tabs)),
    ));
    await t.pumpAndSettle();
    expect(find.text('作者'), findsOneWidget);
    expect(find.text('分析'), findsOneWidget);
    expect(find.text('作者正文'), findsOneWidget);
    await t.tap(find.text('分析'));
    await t.pumpAndSettle();
    expect(find.text('分析正文'), findsOneWidget);
  });

  testWidgets('提供 artist →「作者介绍」为首位 tab、默认选中、可切走', (t) async {
    await t.pumpWidget(ProviderScope(
        child: MaterialApp(
      localizationsDelegates: AppLocalizations.localizationsDelegates,
      supportedLocales: AppLocalizations.supportedLocales,
      locale: const Locale('zh'),
      theme: AppTheme.lightTheme(),
      home: const Scaffold(
        body: GuideDeepSheetContent(
          tabs: [
            ObjectTab(
                sectionCode: 'analysis',
                label: '分析',
                body: '分析正文',
                hasAudio: false),
          ],
          artist: Artist(name: '马奈', bio: '一段经历'),
          slug: 'orsay',
          qid: 'Q1',
          language: 'zh',
        ),
      ),
    )));
    await t.pumpAndSettle();
    // 作者介绍 tab 存在且默认选中 → 显示作者信息（含音频条与 bio）
    expect(find.text('作者介绍'), findsOneWidget);
    expect(find.text('分析'), findsOneWidget);
    expect(find.text('马奈'), findsOneWidget);
    expect(find.text('一段经历'), findsOneWidget);
    expect(find.text('听讲解'), findsOneWidget); // 作者 tab 也有音频条
    expect(find.text('分析正文'), findsNothing); // 未选中不显示
    // 切到「分析」→ 作者内容让位给分析正文
    await t.tap(find.text('分析'));
    await t.pumpAndSettle();
    expect(find.text('分析正文'), findsOneWidget);
    expect(find.text('马奈'), findsNothing);
  });

  // ── 切 tab 时音频不跟着换（用户实测反馈）的回归闸 ──────────────────────
  // 洞在这里：两个 tab 都有正文时,播放条在 Column 里位置/类型都不变,Flutter
  // 原地复用 State,播放器实例没动 → 继续放上一段。修法是 didUpdateWidget 按
  // audioSourceId 复位。下面这条钉住"复用"这个前提：一旦有人给播放条加了 Key
  // 让它重建,这条会红,提醒去掉已成死码的 didUpdateWidget。
  testWidgets('切 tab：播放条 State 原地复用,section 换成新 tab 的', (t) async {
    await t.pumpWidget(ProviderScope(
        child: MaterialApp(
      localizationsDelegates: AppLocalizations.localizationsDelegates,
      supportedLocales: AppLocalizations.supportedLocales,
      locale: const Locale('zh'),
      theme: AppTheme.lightTheme(),
      home: const Scaffold(
        body: GuideDeepSheetContent(
          tabs: [
            ObjectTab(
                sectionCode: 'analysis',
                label: '分析',
                body: '分析正文',
                hasAudio: true),
            ObjectTab(
                sectionCode: 'context',
                label: '背景',
                body: '背景正文',
                hasAudio: true),
          ],
          slug: 'orangerie',
          qid: 'Q21849357',
          language: 'zh',
        ),
      ),
    )));
    await t.pumpAndSettle();

    final finder = find.byType(GuideAudioPlayer);
    final before = t.state(finder);
    expect((before.widget as GuideAudioPlayer).section, 'analysis');

    await t.tap(find.text('背景'));
    await t.pumpAndSettle();

    expect(identical(t.state(finder), before), isTrue,
        reason: 'State 若不再复用,didUpdateWidget 就成了死码');
    expect((t.state(finder).widget as GuideAudioPlayer).section, 'context');
  });

  test('audioSourceId 认得出四种换段：qid/语言/section/问答序号', () {
    const base = GuideAudioPlayer(slug: 's', qid: 'Q1', language: 'zh');
    expect(
        audioSourceId(base),
        audioSourceId(
            const GuideAudioPlayer(slug: '别的馆', qid: 'Q1', language: 'zh')),
        reason: 'slug 不进身份：同一段换个馆名前缀不该打断播放');
    for (final other in [
      const GuideAudioPlayer(slug: 's', qid: 'Q2', language: 'zh'),
      const GuideAudioPlayer(slug: 's', qid: 'Q1', language: 'en'),
      const GuideAudioPlayer(
          slug: 's', qid: 'Q1', language: 'zh', section: 'analysis'),
      const GuideAudioPlayer(
          slug: 's', qid: 'Q1', language: 'zh', section: 'qa', qaSort: 0),
      const GuideAudioPlayer(
          slug: 's', qid: 'Q1', language: 'zh', section: 'qa', qaSort: 1),
    ]) {
      expect(audioSourceId(base) == audioSourceId(other), isFalse,
          reason: '${other.section}/${other.qaSort} 应算换段');
    }
  });
}
