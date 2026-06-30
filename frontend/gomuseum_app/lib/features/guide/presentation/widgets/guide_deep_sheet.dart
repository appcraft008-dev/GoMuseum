import 'package:flutter/material.dart';
import 'package:gomuseum_app/features/content/data/models/object_content_model.dart';
import 'package:gomuseum_app/features/guide/presentation/widgets/guide_artist_card.dart';
import 'package:gomuseum_app/features/guide/presentation/widgets/guide_audio_bar.dart';
import 'package:gomuseum_app/l10n/app_localizations.dart';
import 'package:gomuseum_app/theme/gm_theme_x.dart';
import 'package:gomuseum_app/theme/gm_tokens.dart';
import 'package:gomuseum_app/ui/gm/gm_icon.dart';

/// 拉起「深度内容」底部抽屉。作者卡（若有）置于首位、必选常驻。
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
    final hasTabs = widget.tabs.isNotEmpty;
    final tab = hasTabs ? widget.tabs[_i] : null;
    final hasBody = tab?.hasBody ?? false;
    final showArtist = widget.artist != null && widget.artist!.name.isNotEmpty;

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
          // 内容：作者卡（首位常驻）→ 深度 tab
          Flexible(
            child: SingleChildScrollView(
              padding: const EdgeInsets.only(bottom: 24),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  if (showArtist)
                    Padding(
                      padding: const EdgeInsets.symmetric(horizontal: 20),
                      child: GuideArtistCard(artist: widget.artist!),
                    ),
                  if (hasTabs) ...[
                    if (showArtist) const SizedBox(height: 18),
                    // Tab 栏（横滚）
                    SingleChildScrollView(
                      scrollDirection: Axis.horizontal,
                      padding: const EdgeInsets.only(left: 12),
                      child: Row(
                        children: [
                          for (int i = 0; i < widget.tabs.length; i++)
                            GestureDetector(
                              behavior: HitTestBehavior.opaque,
                              onTap: () => setState(() => _i = i),
                              child: Container(
                                padding:
                                    const EdgeInsets.fromLTRB(14, 9, 14, 8),
                                decoration: BoxDecoration(
                                  border: Border(
                                    bottom: BorderSide(
                                      color: i == _i
                                          ? gm.accent
                                          : Colors.transparent,
                                      width: 2.5,
                                    ),
                                  ),
                                ),
                                child: Text(
                                  widget.tabs[i].label,
                                  style: i == _i
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
                    // 音频条 + 正文
                    Padding(
                      padding: const EdgeInsets.fromLTRB(20, 11, 20, 0),
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.stretch,
                        children: [
                          GuideAudioBar(audioUrl: tab!.audioUrl),
                          const SizedBox(height: 14),
                          Text(
                            hasBody ? tab.body! : l10n.toBeRefined,
                            style: GmText.sans(
                                size: 13.5,
                                height: 1.95,
                                color: hasBody ? gm.ink : gm.faint),
                            textAlign: TextAlign.justify,
                          ),
                        ],
                      ),
                    ),
                  ],
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }
}
