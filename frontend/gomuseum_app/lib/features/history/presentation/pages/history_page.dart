/// GoMuseum 足迹页 — 暖纸手册定稿（FinalFootprints）
///
/// 刊头标题 + 统计行 + 目录编号分组（后端足迹无博物馆字段，按日期分组）
/// + 条目（缩略图 / 名称 / 时间 / 标星）。
library;

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:gomuseum_app/features/guide/presentation/pages/guide_page.dart';
import 'package:gomuseum_app/features/history/domain/entities/history_item.dart';
import 'package:gomuseum_app/features/history/presentation/providers/history_providers.dart';
import 'package:gomuseum_app/features/recognition/domain/entities/recognition_result.dart';
import 'package:gomuseum_app/theme/gm_palette.dart';
import 'package:gomuseum_app/theme/gm_theme_x.dart';
import 'package:gomuseum_app/ui/gm/gm.dart';

class HistoryPage extends ConsumerStatefulWidget {
  const HistoryPage({super.key});

  @override
  ConsumerState<HistoryPage> createState() => _HistoryPageState();
}

class _HistoryPageState extends ConsumerState<HistoryPage> {
  /// 本地标星（足迹收藏接口接入前仅会话内有效）
  final Set<String> _starred = {};

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
                '足 迹',
                style: GmText.serif(
                    size: 21, weight: FontWeight.w700, letterSpacing: 4),
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
    if (items.isEmpty) return '还没有足迹';
    final days = items
        .map((i) =>
            '${i.timestamp.year}-${i.timestamp.month}-${i.timestamp.day}')
        .toSet()
        .length;
    return '${items.length} 件作品 · $days 天';
  }

  List<Widget> _content(GmPalette gm, HistoryState history) {
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
              Text('足迹加载失败',
                  style: GmText.serif(size: 15, weight: FontWeight.w700)),
              const SizedBox(height: 6),
              Text(history.error!,
                  textAlign: TextAlign.center,
                  style: GmText.sans(size: 12, color: gm.sub)),
              const SizedBox(height: 14),
              GmTicketButton(
                label: '重试',
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
              Text('识别过的展品会自动记录在这里',
                  style: GmText.sans(size: 12.5, color: gm.sub)),
              const SizedBox(height: 16),
              GmTicketButton(
                label: '去识别第一件作品',
                icon: GmIcons.camera,
                onTap: () => context.push('/camera'),
              ),
            ],
          ),
        ),
      ];
    }

    final groups = _groupByDay(history.items);
    final widgets = <Widget>[];
    var index = 0;
    for (final entry in groups.entries) {
      index++;
      widgets.add(Padding(
        padding: const EdgeInsets.only(top: 20),
        child: GmSectionHead(
          number: index.toString().padLeft(2, '0'),
          label: entry.key,
          note: '${entry.value.length} 件',
        ),
      ));
      for (final item in entry.value) {
        widgets.add(_itemRow(gm, item));
      }
    }
    return widgets;
  }

  Map<String, List<HistoryItem>> _groupByDay(List<HistoryItem> items) {
    final sorted = [...items]
      ..sort((a, b) => b.timestamp.compareTo(a.timestamp));
    final groups = <String, List<HistoryItem>>{};
    for (final item in sorted) {
      groups.putIfAbsent(_dayLabel(item.timestamp), () => []).add(item);
    }
    return groups;
  }

  String _dayLabel(DateTime t) {
    final now = DateTime.now();
    final today = DateTime(now.year, now.month, now.day);
    final day = DateTime(t.year, t.month, t.day);
    final diff = today.difference(day).inDays;
    if (diff == 0) return '今天';
    if (diff == 1) return '昨天';
    return '${t.month}月${t.day}日';
  }

  Widget _itemRow(GmPalette gm, HistoryItem item) {
    final starred = _starred.contains(item.id);
    final time =
        '${item.timestamp.hour.toString().padLeft(2, '0')}:${item.timestamp.minute.toString().padLeft(2, '0')}';
    return InkWell(
      onTap: () => _openGuide(item),
      onLongPress: () => _confirmDelete(gm, item),
      child: Padding(
        padding: const EdgeInsets.symmetric(vertical: 9),
        child: Row(
          children: [
            const GmThumb(image: null, size: 46),
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
                    '$time · ${item.artist}',
                    style: GmText.sans(size: 11.5, color: gm.sub),
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                  ),
                ],
              ),
            ),
            GestureDetector(
              behavior: HitTestBehavior.opaque,
              onTap: () => setState(() {
                starred ? _starred.remove(item.id) : _starred.add(item.id);
              }),
              child: GmIcon(
                GmIcons.star,
                size: 18,
                color: starred ? gm.accent : gm.line,
                fill: starred,
              ),
            ),
          ],
        ),
      ),
    );
  }

  void _openGuide(HistoryItem item) {
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
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (dialogContext) => AlertDialog(
        backgroundColor: gm.surface,
        title: Text('删除这条足迹？',
            style: GmText.serif(size: 16, weight: FontWeight.w700)),
        content: Text(item.artworkName, style: GmText.sans(size: 13)),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(dialogContext, false),
            child: Text('取消', style: GmText.sans(size: 13, color: gm.sub)),
          ),
          TextButton(
            onPressed: () => Navigator.pop(dialogContext, true),
            child:
                Text('删除', style: GmText.sans(size: 13, color: GmColors.error)),
          ),
        ],
      ),
    );
    if (confirmed == true) {
      await ref.read(historyProvider.notifier).deleteItem(item.id);
    }
  }
}
