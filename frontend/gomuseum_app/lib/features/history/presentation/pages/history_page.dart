/// GoMuseum 足迹页 — 暖纸手册定稿（FinalFootprints）
///
/// 刊头标题 + 统计行 + **按「一次参观」（同一天 × 同一个馆）分组** + 条目
/// （缩略图 / 名称 / 时间 / 艺术家）。分组规则见 `footprint_visit.dart`。
///
/// 馆名与城市**不在足迹响应里** —— 足迹只给 `museum_slug`，名字从
/// `museumsListProvider` 就地查。这是纯呈现，不动契约。
library;

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:gomuseum_app/features/content/data/models/museum_summary_model.dart';
import 'package:gomuseum_app/features/content/presentation/providers/catalog_providers.dart';
import 'package:gomuseum_app/features/guide/presentation/pages/guide_page.dart';
import 'package:gomuseum_app/features/history/domain/entities/history_item.dart';
import 'package:gomuseum_app/features/history/presentation/footprint_visit.dart';
import 'package:gomuseum_app/features/history/presentation/providers/history_providers.dart';
import 'package:gomuseum_app/features/recognition/domain/entities/recognition_result.dart';
import 'package:gomuseum_app/l10n/app_localizations.dart';
import 'package:gomuseum_app/theme/gm_palette.dart';
import 'package:gomuseum_app/theme/gm_theme_x.dart';
import 'package:gomuseum_app/ui/gm/gm.dart';

class HistoryPage extends ConsumerStatefulWidget {
  const HistoryPage({super.key});

  @override
  ConsumerState<HistoryPage> createState() => _HistoryPageState();
}

class _HistoryPageState extends ConsumerState<HistoryPage> {
  @override
  Widget build(BuildContext context) {
    final gm = context.gm;
    final history = ref.watch(historyProvider);

    return SafeArea(
      bottom: false,
      child: RefreshIndicator(
        color: gm.accent,
        onRefresh: () => ref.read(historyProvider.notifier).refresh(),
        child: SingleChildScrollView(
          physics: const AlwaysScrollableScrollPhysics(),
          padding: const EdgeInsets.fromLTRB(26, 16, 26, 12),
          child: Column(
            children: [
              Text(
                AppLocalizations.of(context)!.footprintTitle,
                style: GmText.serif(
                    size: 21,
                    weight: FontWeight.w700,
                    letterSpacing: context.gmLetterSpacing(4)),
              ),
              const SizedBox(height: 8),
              const GmDiamond(width: 110),
              const SizedBox(height: 8),
              Text(
                _statsLine(history.items),
                style: GmText.sans(size: 11.5, letterSpacing: 1, color: gm.sub),
              ),
              const SizedBox(height: 4),
              ..._content(gm, history),
            ],
          ),
        ),
      ),
    );
  }

  String _statsLine(List<HistoryItem> items) {
    final l10n = AppLocalizations.of(context)!;
    if (items.isEmpty) return l10n.noFootprints;
    final days = items
        .map((i) =>
            '${i.timestamp.year}-${i.timestamp.month}-${i.timestamp.day}')
        .toSet()
        .length;
    return l10n.footprintStat(items.length, days);
  }

  List<Widget> _content(GmPalette gm, HistoryState history) {
    final l10n = AppLocalizations.of(context)!;
    if (history.isLoading && history.items.isEmpty) {
      return const [
        Padding(
          padding: EdgeInsets.symmetric(vertical: 60),
          child: CircularProgressIndicator(),
        ),
      ];
    }
    if (history.error != null && history.items.isEmpty) {
      return [
        Padding(
          padding: const EdgeInsets.symmetric(vertical: 40),
          child: Column(
            children: [
              Text(l10n.footprintLoadFailed,
                  style: GmText.serif(size: 15, weight: FontWeight.w700)),
              const SizedBox(height: 6),
              Text(history.error!,
                  textAlign: TextAlign.center,
                  style: GmText.sans(size: 12, color: gm.sub)),
              const SizedBox(height: 14),
              GmTicketButton(
                label: l10n.retry,
                height: 38,
                onTap: () => ref.read(historyProvider.notifier).refresh(),
              ),
            ],
          ),
        ),
      ];
    }
    if (history.items.isEmpty) {
      return [
        Padding(
          padding: const EdgeInsets.symmetric(vertical: 40),
          child: Column(
            children: [
              GmIcon(GmIcons.pin, size: 40, color: gm.faint),
              const SizedBox(height: 12),
              Text(l10n.footprintEmptyHint,
                  style: GmText.sans(size: 12.5, color: gm.sub)),
              const SizedBox(height: 16),
              GmTicketButton(
                label: l10n.footprintGoRecognize,
                icon: GmIcons.camera,
                onTap: () => context.push('/camera'),
              ),
            ],
          ),
        ),
      ];
    }

    // 馆列表拿不到就先用 slug 兜底：足迹本身已经能显示了，不该被另一个请求卡住。
    // 足迹要跑一圈 hydrate，几乎总比这个扁平列表慢 —— 兜底是个短暂瞬态。
    final museums = <String, MuseumSummary>{
      for (final m in ref.watch(museumsListProvider).valueOrNull ??
          const <MuseumSummary>[])
        m.slug: m,
    };
    final lang = Localizations.localeOf(context).languageCode;

    final visits = groupFootprintsByVisit(history.items);
    final showCity = footprintsSpanCities(
      visits.map((v) => museums[v.museumSlug]?.localizedCity(lang) ?? ''),
    );

    final widgets = <Widget>[];
    String? lastCity;
    var index = 0;
    for (final visit in visits) {
      final museum = museums[visit.museumSlug];
      if (showCity) {
        final city = museum?.localizedCity(lang) ?? '';
        // 城市未知时不发标题、也不动 lastCity：把"巴黎 → 未知 → 巴黎"
        // 断成两段巴黎，是在用缺数据制造一次不存在的行程。
        if (city.isNotEmpty && city != lastCity) {
          widgets.add(_cityHead(gm, city));
          lastCity = city;
        }
      }
      index++;
      widgets.add(Padding(
        padding: const EdgeInsets.only(top: 20),
        child: GmSectionHead(
          number: index.toString().padLeft(2, '0'),
          label: museum?.localizedName(lang) ??
              visit.museumSlug ??
              l10n.footprintNoMuseum,
          note:
              '${_dayLabel(visit.day)} · ${l10n.itemsCount(visit.items.length)}',
        ),
      ));
      for (final item in visit.items) {
        widgets.add(_itemRow(gm, item));
      }
    }
    return widgets;
  }

  Widget _cityHead(GmPalette gm, String city) => Padding(
        padding: const EdgeInsets.only(top: 26),
        child: Row(
          children: [
            GmIcon(GmIcons.pin, size: 13, color: gm.accent),
            const SizedBox(width: 7),
            Text(
              city,
              style: GmText.serif(
                size: 14,
                weight: FontWeight.w700,
                letterSpacing: context.gmLetterSpacing(2),
              ),
            ),
          ],
        ),
      );

  /// 只负责**显示**，不参与分组 —— 分组键是真实日期（见 `footprint_visit.dart`）。
  String _dayLabel(DateTime t) {
    final l10n = AppLocalizations.of(context)!;
    final now = DateTime.now();
    final today = DateTime(now.year, now.month, now.day);
    final day = DateTime(t.year, t.month, t.day);
    final diff = today.difference(day).inDays;
    if (diff == 0) return l10n.today;
    if (diff == 1) return l10n.yesterday;
    // 跨年才带年份：「过了很长时间后回头看」时，不写年份的 9月18日 谁也认不出是哪年。
    // ⚠️ 参数顺序是 **(day, month, year)**，不是模板里 `{month}/{day}/{year}` 的顺序
    // —— gen-l10n 对三个占位符重排过，而生成的形参全是 `Object`，写反了照样编译，
    // 只在屏幕上变成「9年18月2026日」。`footprint_test.dart` 钉着这条。
    if (t.year != now.year)
      return l10n.dateYearMonthDay(t.day, t.month, t.year);
    return l10n.dateMonthDay(t.month, t.day);
  }

  Widget _itemRow(GmPalette gm, HistoryItem item) {
    final time =
        '${item.timestamp.hour.toString().padLeft(2, '0')}:${item.timestamp.minute.toString().padLeft(2, '0')}';
    return InkWell(
      onTap: () => _openGuide(item),
      onLongPress: () => _confirmDelete(gm, item),
      child: Padding(
        padding: const EdgeInsets.symmetric(vertical: 9),
        child: Row(
          children: [
            GmThumb(
              image:
                  item.thumbnail == null ? null : NetworkImage(item.thumbnail!),
              size: 46,
            ),
            const SizedBox(width: 13),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    item.artworkName,
                    style: GmText.serif(size: 14.5, weight: FontWeight.w600),
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                  ),
                  const SizedBox(height: 3),
                  Text(
                    // 艺术家可能是空的（作者不详／富化没覆盖到），
                    // 那就只显示时间，别留一个孤零零的分隔点
                    item.artist.isEmpty ? time : '$time · ${item.artist}',
                    style: GmText.sans(size: 11.5, color: gm.sub),
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }

  void _openGuide(HistoryItem item) {
    // `GuideArgs` 有两条路。slug+qid 走馆藏那条，能拿到完整讲解；
    // 只给 result 走的是"刚拍完照"那条，而讲解正文并不在足迹数据里——
    // 从足迹点进去看到一页空讲解，等于这个 tab 只是看着能点。
    if (item.hasGuide) {
      context.push(
        '/guide',
        extra: GuideArgs(
          slug: item.museumSlug,
          qid: item.qid,
          imageUrl: item.thumbnail,
        ),
      );
      return;
    }
    // 老后端不返回 slug/qid 时的兜底，保持原行为。
    context.push(
      '/guide',
      extra: GuideArgs(
        result: RecognitionResult(
          id: item.id,
          artworkName: item.artworkName,
          artist: item.artist,
          period: item.period,
          description: item.description,
          confidence: item.confidence,
          timestamp: item.timestamp,
        ),
      ),
    );
  }

  Future<void> _confirmDelete(GmPalette gm, HistoryItem item) async {
    final l10n = AppLocalizations.of(context)!;
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (dialogContext) => AlertDialog(
        backgroundColor: gm.surface,
        title: Text(l10n.deleteFootprintQ,
            style: GmText.serif(size: 16, weight: FontWeight.w700)),
        content: Text(item.artworkName, style: GmText.sans(size: 13)),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(dialogContext, false),
            child:
                Text(l10n.cancel, style: GmText.sans(size: 13, color: gm.sub)),
          ),
          TextButton(
            onPressed: () => Navigator.pop(dialogContext, true),
            child: Text(l10n.delete,
                style: GmText.sans(size: 13, color: GmColors.error)),
          ),
        ],
      ),
    );
    if (confirmed == true) {
      await ref.read(historyProvider.notifier).deleteItem(item.id);
    }
  }
}
