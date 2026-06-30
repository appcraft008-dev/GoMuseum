import 'package:flutter/material.dart';
import 'package:gomuseum_app/features/content/data/models/object_content_model.dart';
import 'package:gomuseum_app/l10n/app_localizations.dart';
import 'package:gomuseum_app/theme/gm_theme_x.dart';
import 'package:gomuseum_app/theme/gm_tokens.dart';
import 'package:gomuseum_app/ui/gm/gm_atoms.dart';

/// 作者卡（必选常驻）：◆ 作者 小节 + 边框卡。
/// 姓名一定有；生卒/国籍/代表作/经历缺啥不显啥。
class GuideArtistCard extends StatelessWidget {
  const GuideArtistCard({super.key, required this.artist});

  final Artist artist;

  /// 生卒年 · 国籍（缺项跳过；全缺则 null）。
  String? _metaLine() {
    final b = artist.birth, d = artist.death;
    String? years;
    if (b != null && d != null) {
      years = '$b – $d';
    } else if (b != null) {
      years = '$b –';
    } else if (d != null) {
      years = '– $d';
    }
    final parts = <String>[
      if (years != null) years,
      if (artist.nationality != null) artist.nationality!,
    ];
    return parts.isEmpty ? null : parts.join(' · ');
  }

  @override
  Widget build(BuildContext context) {
    final gm = context.gm;
    final l10n = AppLocalizations.of(context)!;
    final meta = _metaLine();
    final hasWorks = artist.notableWorks.isNotEmpty;
    final hasBio = (artist.bio ?? '').trim().isNotEmpty;

    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        // ◆ 作者 小节头
        Padding(
          padding: const EdgeInsets.only(top: 18, bottom: 12),
          child: Row(children: [
            Text('◆  ${l10n.guideArtist}',
                style: GmText.serif(
                    size: 12.5,
                    weight: FontWeight.w700,
                    color: gm.accentDeep,
                    letterSpacing: 2)),
            const SizedBox(width: 10),
            Expanded(child: Container(height: 1, color: gm.line)),
          ]),
        ),
        // 边框卡
        Container(
          padding: const EdgeInsets.fromLTRB(14, 13, 14, 14),
          decoration: BoxDecoration(
            color: gm.surface,
            border: Border.all(color: gm.line),
          ),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(artist.name,
                  style: GmText.serif(size: 16, weight: FontWeight.w700)),
              if (meta != null) ...[
                const SizedBox(height: 5),
                Text(meta, style: GmText.sans(size: 12, color: gm.sub)),
              ],
              if (hasWorks) ...[
                const SizedBox(height: 5),
                Text(
                    '${l10n.guideNotableWorks}：${artist.notableWorks.join(' · ')}',
                    style: GmText.sans(size: 12, color: gm.sub)),
              ],
              if (hasBio) ...[
                const Padding(
                  padding: EdgeInsets.symmetric(vertical: 11),
                  child: GmHairline(),
                ),
                Text(artist.bio!,
                    style: GmText.sans(size: 13.5, height: 1.9),
                    textAlign: TextAlign.justify),
              ],
            ],
          ),
        ),
      ],
    );
  }
}
