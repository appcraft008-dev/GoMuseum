/// 拍照命中必看作品时,讲解页顶部的临时盖章提示(spec 2026-10-27 必看打卡 §五.6)。
///
/// 几秒后自动收起;**点了也不跳**(不打断正在播的讲解)。只在快门现场拍的识别进来时
/// 由讲解页调用;这家馆没有必看清单就连请求都不发。
library;

import 'dart:async';
import 'dart:math' as math;

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:gomuseum_app/core/network/image_request.dart';
import 'package:gomuseum_app/features/content/presentation/providers/catalog_providers.dart';
import 'package:gomuseum_app/features/must_see/data/must_see_providers.dart';
import 'package:gomuseum_app/features/must_see/presentation/passport_page.dart';
import 'package:gomuseum_app/l10n/app_localizations.dart';
import 'package:gomuseum_app/theme/gm_theme_x.dart';
import 'package:gomuseum_app/ui/gm/gm.dart';

const _shownFor = Duration(seconds: 4);

Future<void> maybeShowStampToast(
  BuildContext context,
  WidgetRef ref, {
  required String slug,
  required String qid,
  Future<void>? pendingConfirm,
}) async {
  // 馆列表全 App 缓存(首页已拉);冷启动直接进识别时这里补拉一次,不额外多请求
  final bool hasList;
  try {
    hasList = (await ref.read(museumsListProvider.future))
        .any((m) => m.slug == slug && m.mustSeeCount > 0);
  } catch (_) {
    return;
  }
  if (!hasList || !context.mounted) return;
  // 候选确认是 fire-and-forget:先等它提交,否则后端还没这条打卡(慢网下常超过 2 秒)
  if (pendingConfirm != null) {
    try {
      await pendingConfirm;
    } catch (_) {}
  }
  if (!context.mounted) return;
  // 护照页回来也该是新进度:先作废缓存再读
  ref.invalidate(mustSeeProvider(slug));
  final sub = ref.listenManual(mustSeeProvider(slug), (_, __) {});
  try {
    final d = await ref.read(mustSeeProvider(slug).future);
    if (!context.mounted || !d.checked.containsKey(qid)) return;
    final l10n = AppLocalizations.of(context)!;
    final total = d.items.length;
    final item = d.items.firstWhere((i) => i.qid == qid);
    final title = d.completed
        ? l10n.mustSeeToastDone(total)
        : l10n.mustSeeToastStamped(d.checkedCount, total);
    final loc =
        item.location == null ? null : locationText(l10n, item.location!);
    final overlay = Overlay.of(context);
    final entry = OverlayEntry(
      builder: (ctx) => Positioned(
        left: 14,
        right: 14,
        top: MediaQuery.paddingOf(ctx).top + 14,
        // 点了也不跳:整条不接收点击,点到的是下面的讲解页
        child: IgnorePointer(
          child: _Toast(title: title, sub: loc, thumbnail: item.thumbnail),
        ),
      ),
    );
    overlay.insert(entry);
    await Future<void>.delayed(_shownFor);
    entry.remove();
  } catch (_) {
    // 拉不到进度就不提示:提示是锦上添花,不能打扰讲解
  } finally {
    sub.close();
  }
}

class _Toast extends StatelessWidget {
  const _Toast({required this.title, this.sub, this.thumbnail});

  final String title;
  final String? sub;
  final String? thumbnail;

  @override
  Widget build(BuildContext context) {
    final gm = context.gm;
    return Material(
      color: Colors.transparent,
      child: Container(
        padding: const EdgeInsets.fromLTRB(12, 10, 12, 10),
        decoration: BoxDecoration(
          color: gm.surface,
          border: Border.all(color: gm.line),
          borderRadius: BorderRadius.circular(12),
          boxShadow: const [
            BoxShadow(
                color: Color(0x40000000), blurRadius: 18, offset: Offset(0, 6)),
          ],
        ),
        child: Row(children: [
          Transform.rotate(
            angle: -8 * math.pi / 180,
            child: Container(
              width: 40,
              height: 40,
              padding: const EdgeInsets.all(2),
              decoration: BoxDecoration(
                shape: BoxShape.circle,
                border: Border.all(color: gm.accent, width: 2),
              ),
              child: ClipOval(
                child: thumbnail == null
                    ? ColoredBox(color: gm.chipBg)
                    : Image.network(sizedImageUrl(thumbnail!, 120),
                        fit: BoxFit.cover,
                        cacheWidth: 120,
                        headers: kImageRequestHeaders,
                        errorBuilder: (_, __, ___) =>
                            ColoredBox(color: gm.chipBg)),
              ),
            ),
          ),
          const SizedBox(width: 10),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              mainAxisSize: MainAxisSize.min,
              children: [
                Text(title,
                    style: GmText.sans(
                        size: 13, weight: FontWeight.w700, color: gm.ink)),
                if (sub != null && sub!.isNotEmpty)
                  Text(sub!, style: GmText.sans(size: 11, color: gm.sub)),
              ],
            ),
          ),
        ]),
      ),
    );
  }
}
