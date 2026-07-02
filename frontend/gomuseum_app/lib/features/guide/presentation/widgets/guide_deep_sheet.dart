import 'package:flutter/material.dart';
import 'package:gomuseum_app/features/content/data/models/object_content_model.dart';
import 'package:gomuseum_app/features/guide/presentation/widgets/guide_artist_card.dart';
import 'package:gomuseum_app/features/guide/presentation/widgets/guide_audio_bar.dart';
import 'package:gomuseum_app/l10n/app_localizations.dart';
import 'package:gomuseum_app/theme/gm_palette.dart';
import 'package:gomuseum_app/theme/gm_theme_x.dart';
import 'package:gomuseum_app/theme/gm_tokens.dart';
import 'package:gomuseum_app/ui/gm/gm_icon.dart';

/// 拉起「深度内容」底部抽屉。作者（若有）作为首位「作者介绍」tab、必选常驻。
Future<void> showGuideDeepSheet(BuildContext context, List<ObjectTab> tabs,
    {Artist? artist}) {
  final gm = context.gm;
  return showModalBottomSheet<void>(
    context: context,
    isScrollControlled: true,
    backgroundColor: Colors.transparent,
    // 暗色遮罩亦由 token 决定对比；barrierColor 用半透明墨色
    barrierColor: gm.ink.withValues(alpha: 0.32),
    builder: (_) => FractionallySizedBox(
      heightFactor: 0.85,
      child: GuideDeepSheetContent(tabs: tabs, artist: artist),
    ),
  );
}

/// 抽屉内容（抽出便于单测，不依赖 showModalBottomSheet）。
class GuideDeepSheetContent extends StatefulWidget {
  const GuideDeepSheetContent({super.key, required this.tabs, this.artist});
  final List<ObjectTab> tabs;
  final Artist? artist;

  @override
  State<GuideDeepSheetContent> createState() => _GuideDeepSheetContentState();
}

class _GuideDeepSheetContentState extends State<GuideDeepSheetContent> {
  int _i = 0;

  @override
  Widget build(BuildContext context) {
    final gm = context.gm;
    final l10n = AppLocalizations.of(context)!;
    final showArtist = widget.artist != null && widget.artist!.name.isNotEmpty;

    // 统一 tab 顺序：作者介绍（若有，恒首位）→ 深度 tabs。
    final labels = <String>[
      if (showArtist) l10n.guideArtistTab,
      for (final t in widget.tabs) t.label,
    ];
    // 越界保护（重开抽屉时 _i 归 0，一般不触发）。
    final selected = labels.isEmpty ? 0 : _i.clamp(0, labels.length - 1);
    final artistSelected = showArtist && selected == 0;

    return Container(
      decoration: BoxDecoration(
        color: gm.surface,
        border: Border(top: BorderSide(color: gm.line, width: 1.5)),
        borderRadius: const BorderRadius.vertical(top: Radius.circular(18)),
        boxShadow: [
          BoxShadow(
              color: gm.ink.withValues(alpha: 0.13),
              offset: const Offset(0, -8),
              blurRadius: 32),
        ],
      ),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          // 抓手条
          Padding(
            padding: const EdgeInsets.fromLTRB(0, 11, 0, 5),
            child: Center(
              child: Container(
                  width: 38,
                  height: 4,
                  decoration: BoxDecoration(
                      color: gm.faint, borderRadius: BorderRadius.circular(2))),
            ),
          ),
          // 标题行
          Padding(
            padding: const EdgeInsets.fromLTRB(20, 2, 20, 10),
            child: Row(
              children: [
                Text(l10n.guideDeepContent,
                    style: GmText.serif(size: 17, weight: FontWeight.w700)),
                const Spacer(),
                GestureDetector(
                  behavior: HitTestBehavior.opaque,
                  onTap: () => Navigator.of(context).maybePop(),
                  child: GmIcon(GmIcons.close, size: 19, color: gm.faint),
                ),
              ],
            ),
          ),
          Container(height: 1.5, color: gm.line),
          // Tab 栏（横滚，粘顶）
          SingleChildScrollView(
            scrollDirection: Axis.horizontal,
            padding: const EdgeInsets.only(left: 12),
            child: Row(
              children: [
                for (int i = 0; i < labels.length; i++)
                  GestureDetector(
                    behavior: HitTestBehavior.opaque,
                    onTap: () => setState(() => _i = i),
                    child: Container(
                      padding: const EdgeInsets.fromLTRB(14, 9, 14, 8),
                      decoration: BoxDecoration(
                        border: Border(
                          bottom: BorderSide(
                            color:
                                i == selected ? gm.accent : Colors.transparent,
                            width: 2.5,
                          ),
                        ),
                      ),
                      child: Text(
                        labels[i],
                        style: i == selected
                            ? GmText.serif(
                                size: 13.5,
                                weight: FontWeight.w700,
                                color: gm.accentDeep)
                            : GmText.sans(size: 13.5, color: gm.sub),
                      ),
                    ),
                  ),
              ],
            ),
          ),
          Container(height: 1, color: gm.line),
          // 正文（音频条 + 内容），可滚动
          Flexible(
            child: SingleChildScrollView(
              padding: const EdgeInsets.fromLTRB(20, 11, 20, 24),
              child: artistSelected
                  ? _artistBody()
                  : _tabBody(context, gm, l10n, showArtist, selected),
            ),
          ),
        ],
      ),
    );
  }

  /// 作者介绍 tab：音频条（预留）+ 结构化作者信息。
  Widget _artistBody() {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        const GuideAudioBar(audioUrl: null),
        const SizedBox(height: 14),
        GuideArtistCard(artist: widget.artist!),
      ],
    );
  }

  /// 深度 tab：音频条 + 正文（空则「待完善」）。
  Widget _tabBody(BuildContext context, GmPalette gm, AppLocalizations l10n,
      bool showArtist, int selected) {
    final deepIndex = showArtist ? selected - 1 : selected;
    if (deepIndex < 0 || deepIndex >= widget.tabs.length) {
      return const SizedBox.shrink();
    }
    final tab = widget.tabs[deepIndex];
    final hasBody = tab.hasBody;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        GuideAudioBar(audioUrl: tab.audioUrl),
        const SizedBox(height: 14),
        Text(
          hasBody ? tab.body! : l10n.toBeRefined,
          style: GmText.sans(
              size: 13.5,
              height: context.gmBodyHeight,
              color: hasBody ? gm.ink : gm.faint),
          textAlign: TextAlign.justify,
        ),
      ],
    );
  }
}
