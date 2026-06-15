/// GoMuseum 探索页 — 暖纸手册定稿（FinalExplore）
///
/// 刊头标题 + 搜索框 + 城市 chips + 装裱博物馆大卡 + 目录编号条目列表。
/// 数据为种子数据（馆方/POI 接口接入前的演示内容），搜索为客户端过滤。
library;

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:gomuseum_app/features/explore/data/museum_pack.dart';
import 'package:gomuseum_app/ui/gm/gm.dart';

class _ExploreMuseum {
  const _ExploreMuseum({
    required this.name,
    required this.meta,
    this.openNote,
    this.ticketNote,
    this.distance,
    this.cover,
    this.topWorks = const [],
    this.collectionNote,
  });

  final String name;

  /// 列表条目的一行说明（开放时间 · 票价 · 距离）
  final String meta;

  // 以下仅首个「装裱大卡」使用
  final String? openNote;
  final String? ticketNote;
  final String? distance;
  final GmArtwork? cover;
  final List<GmArtwork> topWorks;
  final String? collectionNote;
}

const Map<String, List<_ExploreMuseum>> _museumsByCity = {
  '巴黎': [
    _ExploreMuseum(
      name: '奥赛博物馆',
      meta: '9:30–21:45 · €16 · 0.8 km',
      openNote: '开放中 · 至 21:45',
      ticketNote: '€16 · 周一闭馆',
      distance: '0.8 km',
      cover: GmArt.orsayHall,
      topWorks: [GmArt.rhone, GmArt.self1889, GmArt.bedroom],
      collectionNote: '含 86 件已收录讲解',
    ),
    _ExploreMuseum(name: '卢浮宫', meta: '9:00–18:00 · €22 · 1.9 km'),
    _ExploreMuseum(name: '橘园美术馆', meta: '9:00–18:00 · €12 · 1.6 km'),
    _ExploreMuseum(name: '罗丹美术馆', meta: '10:00–18:30 · €14 · 2.2 km'),
  ],
  '阿姆斯特丹': [
    _ExploreMuseum(
      name: '梵高博物馆',
      meta: '9:00–18:00 · €22',
      openNote: '开放中 · 至 18:00',
      ticketNote: '€22 · 需预约',
      distance: '—',
      cover: GmArt.crows,
      topWorks: [GmArt.crows, GmArt.thunder, GmArt.self1887],
      collectionNote: '含 42 件已收录讲解',
    ),
    _ExploreMuseum(name: '荷兰国家博物馆', meta: '9:00–17:00 · €22.5'),
    _ExploreMuseum(name: '市立博物馆', meta: '10:00–18:00 · €20'),
  ],
  '伦敦': [
    _ExploreMuseum(name: '大英博物馆', meta: '10:00–17:00 · 免费'),
    _ExploreMuseum(name: '国家美术馆', meta: '10:00–18:00 · 免费'),
  ],
  '维也纳': [
    _ExploreMuseum(name: '艺术史博物馆', meta: '10:00–18:00 · €21'),
    _ExploreMuseum(name: '美景宫', meta: '9:00–18:00 · €17.5'),
  ],
};

class ExplorePage extends ConsumerStatefulWidget {
  const ExplorePage({super.key});

  @override
  ConsumerState<ExplorePage> createState() => _ExplorePageState();
}

class _ExplorePageState extends ConsumerState<ExplorePage> {
  String _city = '巴黎';
  String _query = '';

  List<_ExploreMuseum> get _filtered {
    final list = _museumsByCity[_city] ?? const [];
    if (_query.trim().isEmpty) return list;
    final q = _query.trim().toLowerCase();
    return list.where((m) => m.name.toLowerCase().contains(q)).toList();
  }

  @override
  Widget build(BuildContext context) {
    final museums = _filtered;
    final showFeature = museums.isNotEmpty && museums.first.cover != null;
    // 巴黎首卡使用真实奥赛馆包数据（加载中/失败时回退种子数据）
    final orsayPack =
        _city == '巴黎' ? ref.watch(museumPackProvider('orsay')).value : null;
    return SafeArea(
      bottom: false,
      child: SingleChildScrollView(
        padding: const EdgeInsets.fromLTRB(26, 16, 26, 12),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Center(
              child: Column(
                children: [
                  Text(
                    '探 索',
                    style: GmText.serif(
                        size: 21, weight: FontWeight.w700, letterSpacing: 4),
                  ),
                  const SizedBox(height: 8),
                  const GmDiamond(width: 110),
                ],
              ),
            ),
            const SizedBox(height: 14),
            _searchBox(),
            const SizedBox(height: 12),
            _cityChips(),
            const SizedBox(height: 22),
            GmSectionHead(
              number: '01',
              label: _city,
              note: '${museums.length} 家博物馆',
            ),
            if (museums.isEmpty)
              Padding(
                padding: const EdgeInsets.symmetric(vertical: 28),
                child: Center(
                  child: Text('没有匹配的博物馆',
                      style: GmText.sans(size: 12.5, color: GmColors.sub)),
                ),
              )
            else ...[
              if (showFeature) ...[
                const SizedBox(height: 13),
                _featureCard(museums.first, pack: orsayPack),
              ],
              for (var i = showFeature ? 1 : 0; i < museums.length; i++)
                _listRow('${(i + 1).toString().padLeft(2, '0')}', museums[i]),
            ],
          ],
        ),
      ),
    );
  }

  Widget _searchBox() {
    return Container(
      height: 46,
      padding: const EdgeInsets.symmetric(horizontal: 16),
      decoration: BoxDecoration(
        color: GmColors.surface,
        border: Border.all(color: GmColors.line),
      ),
      child: Row(
        children: [
          const GmIcon(GmIcons.search, size: 18, color: GmColors.faint),
          const SizedBox(width: 10),
          Expanded(
            child: TextField(
              style: GmText.sans(size: 13.5),
              decoration: InputDecoration(
                hintText: '搜索城市、博物馆或艺术品',
                hintStyle: GmText.sans(size: 13.5, color: GmColors.faint),
                border: InputBorder.none,
                isDense: true,
              ),
              onChanged: (v) => setState(() => _query = v),
            ),
          ),
        ],
      ),
    );
  }

  Widget _cityChips() {
    return SingleChildScrollView(
      scrollDirection: Axis.horizontal,
      child: Row(
        children: [
          for (final city in _museumsByCity.keys) ...[
            GestureDetector(
              onTap: () => setState(() => _city = city),
              child: Container(
                padding:
                    const EdgeInsets.symmetric(horizontal: 15, vertical: 7),
                decoration: BoxDecoration(
                  color: city == _city ? GmColors.ctaBg : Colors.transparent,
                  border: Border.all(
                    color: city == _city ? GmColors.ctaBg : GmColors.line,
                  ),
                ),
                child: Text(
                  city,
                  style: GmText.sans(
                    size: 12.5,
                    color: city == _city ? GmColors.ctaInk : GmColors.sub,
                  ),
                ),
              ),
            ),
            const SizedBox(width: 8),
          ],
        ],
      ),
    );
  }

  Widget _featureCard(_ExploreMuseum museum, {MuseumPack? pack}) {
    return GestureDetector(
      onTap: pack != null ? () => context.push('/museum/${pack.slug}') : null,
      child: Container(
        decoration: BoxDecoration(
          color: GmColors.surface,
          border: Border.all(color: GmColors.line),
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Padding(
              padding: const EdgeInsets.fromLTRB(9, 9, 9, 0),
              child: GmInnerImage(
                image: AssetImage(museum.cover!.asset),
                height: 124,
              ),
            ),
            Padding(
              padding: const EdgeInsets.fromLTRB(14, 12, 14, 14),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    crossAxisAlignment: CrossAxisAlignment.baseline,
                    textBaseline: TextBaseline.alphabetic,
                    children: [
                      Text(museum.name,
                          style:
                              GmText.serif(size: 17, weight: FontWeight.w600)),
                      const Spacer(),
                      Text(
                        museum.openNote ?? '',
                        style: GmText.sans(
                            size: 11.5,
                            color: GmColors.accent,
                            weight: FontWeight.w600),
                      ),
                    ],
                  ),
                  const SizedBox(height: 8),
                  Row(
                    children: [
                      const GmIcon(GmIcons.ticket,
                          size: 14, color: GmColors.faint),
                      const SizedBox(width: 5),
                      Text(museum.ticketNote ?? '',
                          style: GmText.sans(size: 12, color: GmColors.sub)),
                      const SizedBox(width: 14),
                      const GmIcon(GmIcons.pin,
                          size: 14, color: GmColors.faint),
                      const SizedBox(width: 5),
                      Text(museum.distance ?? '',
                          style: GmText.sans(size: 12, color: GmColors.sub)),
                    ],
                  ),
                  const Padding(
                    padding: EdgeInsets.symmetric(vertical: 11),
                    child: GmHairline(),
                  ),
                  Row(
                    children: [
                      if (pack != null && pack.artworks.isNotEmpty)
                        for (final art in pack.artworks.take(3)) ...[
                          GmThumb(
                            image: art.thumb(200) != null
                                ? NetworkImage(art.thumb(200)!) as ImageProvider
                                : null,
                            size: 34,
                          ),
                          const SizedBox(width: 6),
                        ]
                      else
                        for (final work in museum.topWorks) ...[
                          GmThumb(image: AssetImage(work.asset), size: 34),
                          const SizedBox(width: 6),
                        ],
                      const SizedBox(width: 3),
                      Text(
                        pack != null
                            ? '含 ${pack.artworkCount} 件已收录讲解'
                            : (museum.collectionNote ?? ''),
                        style: GmText.sans(size: 11, color: GmColors.sub),
                      ),
                      const Spacer(),
                      const GmIcon(GmIcons.chevR,
                          size: 17, color: GmColors.faint),
                    ],
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _listRow(String number, _ExploreMuseum museum) {
    return Container(
      height: 58,
      decoration: const BoxDecoration(
        border: Border(bottom: BorderSide(color: GmColors.line)),
      ),
      child: Row(
        children: [
          Text(
            number,
            style: GmText.serif(
                size: 13,
                color: GmColors.faint,
                weight: FontWeight.w700,
                letterSpacing: 2),
          ),
          const SizedBox(width: 14),
          Expanded(
            child: Column(
              mainAxisAlignment: MainAxisAlignment.center,
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(museum.name,
                    style: GmText.serif(size: 15, weight: FontWeight.w600)),
                const SizedBox(height: 3),
                Text(museum.meta,
                    style: GmText.sans(size: 11.5, color: GmColors.sub)),
              ],
            ),
          ),
          const GmIcon(GmIcons.chevR, size: 17, color: GmColors.faint),
        ],
      ),
    );
  }
}
