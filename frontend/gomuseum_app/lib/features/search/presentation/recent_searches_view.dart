/// 最近搜索标签:搜索框聚焦且没输入时显示;换行排(不左右滑),没记录就不占地方。
library;

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:gomuseum_app/features/search/data/recent_searches.dart';
import 'package:gomuseum_app/l10n/app_localizations.dart';
import 'package:gomuseum_app/theme/gm_theme_x.dart';
import 'package:gomuseum_app/ui/gm/gm.dart';

class RecentSearchesView extends ConsumerWidget {
  const RecentSearchesView(
      {super.key, required this.scope, required this.onPick});

  final String scope;
  final ValueChanged<String> onPick;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final items = ref.watch(recentSearchesProvider(scope));
    if (items.isEmpty) return const SizedBox.shrink();
    final gm = context.gm;
    final l10n = AppLocalizations.of(context)!;
    final notifier = ref.read(recentSearchesProvider(scope).notifier);
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      mainAxisSize: MainAxisSize.min,
      children: [
        Row(
          children: [
            Expanded(
              child: Text(l10n.recentSearches,
                  style: GmText.sans(
                      size: 11,
                      letterSpacing: 1.5,
                      color: gm.sub,
                      weight: FontWeight.w600)),
            ),
            GestureDetector(
              onTap: notifier.clear,
              behavior: HitTestBehavior.opaque,
              child: Padding(
                padding: const EdgeInsets.all(4),
                child: Text(l10n.recentSearchesClear,
                    style: GmText.sans(size: 11.5, color: gm.sub)),
              ),
            ),
          ],
        ),
        const SizedBox(height: 6),
        Wrap(
          spacing: 8,
          runSpacing: 8,
          children: [
            for (final q in items)
              Container(
                decoration: BoxDecoration(border: Border.all(color: gm.line)),
                child: Row(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    GestureDetector(
                      onTap: () => onPick(q),
                      behavior: HitTestBehavior.opaque,
                      child: Padding(
                        padding: const EdgeInsets.fromLTRB(12, 7, 4, 7),
                        child: ConstrainedBox(
                          constraints: const BoxConstraints(maxWidth: 140),
                          child: Text(q,
                              maxLines: 1,
                              overflow: TextOverflow.ellipsis,
                              style: GmText.sans(size: 12.5)),
                        ),
                      ),
                    ),
                    GestureDetector(
                      key: ValueKey('recent-remove-$q'),
                      onTap: () => notifier.remove(q),
                      behavior: HitTestBehavior.opaque,
                      child: Padding(
                        padding: const EdgeInsets.fromLTRB(4, 7, 10, 7),
                        child: GmIcon(GmIcons.close, size: 12, color: gm.faint),
                      ),
                    ),
                  ],
                ),
              ),
          ],
        ),
      ],
    );
  }
}
