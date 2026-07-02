import 'package:flutter/material.dart';
import 'package:gomuseum_app/l10n/app_localizations.dart';
import 'package:gomuseum_app/theme/gm_theme_x.dart';
import 'package:gomuseum_app/theme/gm_tokens.dart';
import 'package:gomuseum_app/ui/gm/gm_icon.dart';

/// 预留态音频条（TTS 未上线前不显示时长、弱化不可点）。
class GuideAudioBar extends StatelessWidget {
  const GuideAudioBar({super.key, required this.audioUrl, this.label});

  final String? audioUrl;
  final String? label;

  @override
  Widget build(BuildContext context) {
    final gm = context.gm;
    final l10n = AppLocalizations.of(context)!;
    final reserved = audioUrl == null;
    final fg = reserved ? gm.faint : gm.sub;

    return Container(
      margin: const EdgeInsets.only(top: 11),
      padding: const EdgeInsets.fromLTRB(10, 7, 12, 7),
      decoration: BoxDecoration(
        color: gm.surface,
        border: Border.all(color: gm.line),
      ),
      child: Row(
        children: [
          Container(
            width: 27,
            height: 27,
            decoration: BoxDecoration(
              shape: BoxShape.circle,
              border: Border.all(color: gm.faint, width: 1.5),
            ),
            alignment: Alignment.center,
            child: GmIcon(GmIcons.play, size: 12, color: gm.faint, fill: true),
          ),
          const SizedBox(width: 10),
          Text(label ?? l10n.guideListen,
              style: GmText.sans(size: 12, color: fg, letterSpacing: 0.4)),
          const SizedBox(width: 12),
          Expanded(child: Container(height: 1.5, color: gm.line)),
        ],
      ),
    );
  }
}
