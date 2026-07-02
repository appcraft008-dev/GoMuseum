import 'package:flutter/material.dart';
import 'package:gomuseum_app/features/content/data/models/object_content_model.dart';
import 'package:gomuseum_app/l10n/app_localizations.dart';
import 'package:gomuseum_app/theme/gm_theme_x.dart';
import 'package:gomuseum_app/theme/gm_tokens.dart';
import 'package:gomuseum_app/ui/gm/gm_atoms.dart';

/// 作者介绍内容（深度抽屉「作者介绍」tab 的正文，与其它 tab 正文同风格：
/// 无边框卡、无小节头）。姓名一定有；生卒/国籍/代表作/经历缺啥不显啥。
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
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(artist.name,
            style: GmText.serif(size: 18, weight: FontWeight.w700)),
        if (meta != null) ...[
          const SizedBox(height: 6),
          Text(meta, style: GmText.sans(size: 12, color: gm.sub)),
        ],
        if (hasWorks) ...[
          const SizedBox(height: 5),
          Text('${l10n.guideNotableWorks}：${artist.notableWorks.join(' · ')}',
              style: GmText.sans(size: 12, color: gm.sub)),
        ],
        if (hasBio) ...[
          const Padding(
            padding: EdgeInsets.symmetric(vertical: 12),
            child: GmHairline(),
          ),
          Text(artist.bio!,
              style: GmText.sans(size: 13.5, height: 1.9),
              textAlign: TextAlign.justify),
        ],
      ],
    );
  }
}
