/// 馆藏清单页 — 暖纸手册风格目录列表
///
/// 展示馆包内按热度排序的馆藏，点击任意作品直接进入讲解页
///（禁拍照场景 / 到馆前预习的主要入口）。
library;

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:gomuseum_app/features/explore/data/museum_pack.dart';
import 'package:gomuseum_app/features/guide/presentation/pages/guide_page.dart';
import 'package:gomuseum_app/features/recognition/domain/entities/recognition_result.dart';
import 'package:gomuseum_app/theme/gm_palette.dart';
import 'package:gomuseum_app/theme/gm_theme_x.dart';
import 'package:gomuseum_app/ui/gm/gm.dart';

class MuseumPage extends ConsumerWidget {
  const MuseumPage({super.key, required this.slug});

  final String slug;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final gm = context.gm;
    final pack = ref.watch(museumPackProvider(slug));

    return Scaffold(
      backgroundColor: gm.bg,
      body: SafeArea(
        child: Column(
          children: [
            Padding(
              padding: const EdgeInsets.fromLTRB(18, 12, 18, 0),
              child: Row(
                children: [
                  GestureDetector(
                    onTap: () => context.canPop()
                        ? context.pop()
                        : context.go('/explore'),
                    behavior: HitTestBehavior.opaque,
                    child: GmIcon(GmIcons.back, size: 20, color: gm.ink),
                  ),
                  Expanded(
                    child: Text(
                      '馆藏目录',
                      textAlign: TextAlign.center,
                      style: GmText.sans(
                          size: 11, letterSpacing: 3, color: gm.sub),
                    ),
                  ),
                  const SizedBox(width: 20),
                ],
              ),
            ),
            Expanded(
              child: pack.when(
                loading: () => const Center(child: CircularProgressIndicator()),
                error: (e, _) => Center(
                  child: Padding(
                    padding: const EdgeInsets.all(32),
                    child: Column(
                      mainAxisAlignment: MainAxisAlignment.center,
                      children: [
                        Text('馆藏加载失败',
                            style: GmText.serif(
                                size: 15, weight: FontWeight.w700)),
                        const SizedBox(height: 8),
                        Text('$e',
                            maxLines: 3,
                            textAlign: TextAlign.center,
                            style: GmText.sans(size: 11, color: gm.sub)),
                        const SizedBox(height: 14),
                        GmTicketButton(
                          label: '重试',
                          height: 38,
                          onTap: () => ref.invalidate(museumPackProvider(slug)),
                        ),
                      ],
                    ),
                  ),
                ),
                data: (data) => _list(context, gm, data),
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _list(BuildContext context, GmPalette gm, MuseumPack pack) {
    return ListView.builder(
      padding: const EdgeInsets.fromLTRB(26, 8, 26, 20),
      itemCount: pack.artworks.length + 1,
      itemBuilder: (context, index) {
        if (index == 0) {
          return Padding(
            padding: const EdgeInsets.only(bottom: 12),
            child: Column(
              children: [
                Text(
                  pack.nameZh,
                  style: GmText.serif(
                      size: 21, weight: FontWeight.w700, letterSpacing: 4),
                ),
                const SizedBox(height: 8),
                const GmDiamond(width: 110),
                const SizedBox(height: 8),
                Text(
                  '${pack.artworkCount} 件馆藏 · 已收录讲解 · 按热度排序',
                  style:
                      GmText.sans(size: 11.5, letterSpacing: 1, color: gm.sub),
                ),
              ],
            ),
          );
        }
        final art = pack.artworks[index - 1];
        return _artworkRow(context, gm, index, art);
      },
    );
  }

  Widget _artworkRow(
      BuildContext context, GmPalette gm, int number, MuseumPackArtwork art) {
    final thumb = art.thumb(200);
    return InkWell(
      onTap: () => context.push(
        '/guide',
        extra: GuideArgs(
          result: RecognitionResult(
            id: art.qid,
            artworkName: art.titleZh,
            artist: art.artistZh,
            period: art.periodZh,
            description: art.year != null ? '创作于${art.year}年' : '',
            confidence: 1.0,
            timestamp: DateTime.now(),
          ),
          imageUrl: thumb,
        ),
      ),
      child: Container(
        padding: const EdgeInsets.symmetric(vertical: 9),
        decoration: BoxDecoration(
          border: Border(bottom: BorderSide(color: gm.line)),
        ),
        child: Row(
          children: [
            Text(
              number.toString().padLeft(2, '0'),
              style: GmText.serif(
                  size: 13,
                  color: gm.faint,
                  weight: FontWeight.w700,
                  letterSpacing: 2),
            ),
            const SizedBox(width: 12),
            GmInnerImage(
              image: thumb != null ? NetworkImage(thumb) : null,
              width: 46,
              height: 46,
            ),
            const SizedBox(width: 13),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    art.titleZh,
                    style: GmText.serif(size: 14.5, weight: FontWeight.w600),
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                  ),
                  const SizedBox(height: 3),
                  Text(
                    [art.artistZh, if (art.year != null) art.year!].join(' · '),
                    style: GmText.sans(size: 11.5, color: gm.sub),
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                  ),
                ],
              ),
            ),
            GmIcon(GmIcons.headphones, size: 17, color: gm.faint),
          ],
        ),
      ),
    );
  }
}
