/// 馆页「必看」tab:护照页(spec 2026-10-27 必看打卡 §五.6)。
///
/// 样稿:docs/superpowers/specs/2026-10-27-must-see-mockups/passport-v2b.html、
/// medal-styles.html(勋章选 B 圆形奖章)。整页像护照内页,每件一个圆章位;
/// 现场拍照认出一件 → 章位盖上作品图与日期;打满后整页斜盖一枚完成大章,本轮内一直盖着;
/// 页底「我的勋章」= 缩小的完成大章。
library;

import 'dart:math' as math;

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:gomuseum_app/features/auth/presentation/auth_provider.dart';
import 'package:gomuseum_app/core/network/image_request.dart';
import 'package:gomuseum_app/features/guide/data/content_viewed.dart';
import 'package:gomuseum_app/features/guide/presentation/pages/guide_page.dart';
import 'package:gomuseum_app/features/must_see/data/must_see_models.dart';
import 'package:gomuseum_app/features/must_see/data/must_see_providers.dart';
import 'package:gomuseum_app/l10n/app_localizations.dart';
import 'package:gomuseum_app/theme/gm_theme_x.dart';
import 'package:gomuseum_app/ui/gm/gm.dart';
import 'package:share_plus/share_plus.dart';

/// 章位上的日期签(10·27)与勋章上的年月(2026-10):纯数字,十语通用。
String stampDate(DateTime d) => '${d.month}·${d.day}';
String medalMonth(DateTime d) =>
    '${d.year}-${d.month.toString().padLeft(2, '0')}';
String _ymd(DateTime d) =>
    '${medalMonth(d)}-${d.day.toString().padLeft(2, '0')}';

/// 楼层叫法。后端 level 是欧式楼层(0 = 地面层,1 = 地面往上一层,同官网 Niveau);
/// 中日韩习惯「1 楼 = 地面层」,照搬数字会把人带错楼 → 这三种语言换算,其余照官方叫法。
String levelText(AppLocalizations l10n, String lang, int level) {
  if (!const {'zh', 'ja', 'ko'}.contains(lang))
    return l10n.passportLevel(level);
  return level >= 0
      ? l10n.passportLevel(level + 1)
      : l10n.passportBasement(-level);
}

/// 位置拼法:缺哪段跳过,用 " · " 连;侧翼名是官方专名,不翻译。
String locationText(AppLocalizations l10n, String lang, MustSeeLocation loc) =>
    [
      if (loc.wing != null) loc.wing!,
      if (loc.level != null) levelText(l10n, lang, loc.level!),
      if (loc.room != null) l10n.passportRoom(loc.room!),
    ].join(' · ');

class MustSeePassport extends ConsumerWidget {
  const MustSeePassport(
      {super.key, required this.slug, required this.museumName});

  final String slug;
  final String museumName;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final gm = context.gm;
    return ref.watch(mustSeeProvider(slug)).when(
          loading: () => Center(
              child:
                  CircularProgressIndicator(strokeWidth: 2, color: gm.accent)),
          error: (_, __) => Center(
            child: IconButton(
              icon: Icon(Icons.refresh, color: gm.sub),
              onPressed: () => ref.invalidate(mustSeeProvider(slug)),
            ),
          ),
          data: (d) => _Passport(
            slug: slug,
            museumName: museumName,
            data: d,
            // 匿名识别也扣额度但不算打卡(spec §五.2):明说要登录,免得以为拍了没盖上是 bug
            signedOut: switch (ref.watch(currentUserProvider)) {
              AsyncData(value: null) => true,
              _ => false,
            },
          ),
        );
  }
}

class _Passport extends StatelessWidget {
  const _Passport(
      {required this.slug,
      required this.museumName,
      required this.data,
      this.signedOut = false});

  final String slug;
  final String museumName;
  final MustSeeData data;
  final bool signedOut;

  /// (组名, 件) 按 yaml 顺序;有位置的按 (wing, level) 归组,无位置的归最后一组。
  /// 整馆都没位置 → 一组、无组名。
  List<(String?, List<(int, MustSeeItem)>)> _groups(
      AppLocalizations l10n, String lang) {
    final indexed = [
      for (var i = 0; i < data.items.length; i++) (i + 1, data.items[i])
    ];
    if (indexed.every((e) => e.$2.location == null)) return [(null, indexed)];
    final groups = <String, List<(int, MustSeeItem)>>{};
    final none = <(int, MustSeeItem)>[];
    for (final e in indexed) {
      final loc = e.$2.location;
      if (loc == null || (loc.wing == null && loc.level == null)) {
        none.add(e);
        continue;
      }
      final name = locationText(
          l10n, lang, MustSeeLocation(wing: loc.wing, level: loc.level));
      groups.putIfAbsent(name, () => []).add(e);
    }
    return [
      for (final g in groups.entries) (g.key, g.value),
      if (none.isNotEmpty) (l10n.passportNoLocation, none),
    ];
  }

  /// 本轮完成时刻:打满时后端已落勋章,最新一枚就是这一轮的;取不到退回最后一次打卡。
  DateTime get _doneAt => data.medals.isNotEmpty
      ? data.medals.first.completedAt
      : data.checked.values
          .fold(DateTime(2000), (a, b) => b.isAfter(a) ? b : a);

  @override
  Widget build(BuildContext context) {
    final gm = context.gm;
    final l10n = AppLocalizations.of(context)!;
    final done = data.checkedCount, total = data.items.length;
    final sub = [
      l10n.passportStamped(done, total),
      if (data.roundStartedAt != null)
        l10n.passportRoundSince(_ymd(data.roundStartedAt!)),
    ].join(' · ');
    return ListView(
      padding: const EdgeInsets.fromLTRB(14, 12, 14, 28),
      children: [
        if (data.completed)
          Padding(
            padding: const EdgeInsets.only(bottom: 8),
            child: Text(l10n.passportRoundDone,
                style: GmText.sans(
                    size: 13, weight: FontWeight.w600, color: gm.accent)),
          ),
        Stack(
          children: [
            Container(
              padding: const EdgeInsets.fromLTRB(10, 16, 10, 20),
              decoration: BoxDecoration(
                color: gm.surface,
                border: Border.all(color: gm.line),
                borderRadius: BorderRadius.circular(10),
              ),
              child: Column(
                children: [
                  Text(l10n.passportTitle(museumName),
                      textAlign: TextAlign.center,
                      style: GmText.serif(
                          size: 16,
                          weight: FontWeight.w700,
                          letterSpacing: 1.5)),
                  const SizedBox(height: 4),
                  Text(sub,
                      textAlign: TextAlign.center,
                      style: GmText.sans(size: 11.5, color: gm.sub)),
                  if (signedOut)
                    Padding(
                      padding: const EdgeInsets.only(top: 6),
                      child: Text(l10n.passportSignInHint,
                          textAlign: TextAlign.center,
                          style: GmText.sans(size: 12, color: gm.accent)),
                    ),
                  const SizedBox(height: 12),
                  for (final (name, items) in _groups(
                      l10n, Localizations.localeOf(context).languageCode)) ...[
                    if (name != null) _GroupLabel(name),
                    _SlotGrid(slug: slug, items: items, checked: data.checked),
                  ],
                ],
              ),
            ),
            if (data.completed)
              Positioned(
                top: 90,
                left: 0,
                right: 0,
                child: IgnorePointer(
                  child: Center(
                    child: _Seal(
                      key: const Key('passport-seal'),
                      size: 200,
                      title: l10n.passportSealTitle,
                      count: '$total / $total',
                      footer: '$museumName · ${_ymd(_doneAt)}',
                    ),
                  ),
                ),
              ),
          ],
        ),
        if (data.completed)
          Padding(
            padding: const EdgeInsets.only(top: 14),
            child: Center(
              child: FilledButton(
                style: FilledButton.styleFrom(
                    backgroundColor: gm.ctaBg, foregroundColor: gm.ctaInk),
                onPressed: () => SharePlus.instance.share(ShareParams(
                  text:
                      '${l10n.passportShareText(museumName, total, _ymd(_doneAt))}\n'
                      'https://gomuseum.app/',
                )),
                child: Text(l10n.passportShare),
              ),
            ),
          ),
        if (data.medals.isNotEmpty) ...[
          const SizedBox(height: 20),
          Text(l10n.passportMedals,
              style: GmText.sans(size: 12.5, color: gm.sub)),
          const SizedBox(height: 10),
          Wrap(
            spacing: 14,
            runSpacing: 12,
            children: [
              for (final m in data.medals)
                _Seal(
                  size: 84,
                  title: l10n.passportSealTitle,
                  count: '${m.count}/${m.count}',
                  footer: medalMonth(m.completedAt),
                ),
            ],
          ),
        ],
      ],
    );
  }
}

class _GroupLabel extends StatelessWidget {
  const _GroupLabel(this.text);
  final String text;

  @override
  Widget build(BuildContext context) {
    final gm = context.gm;
    return Padding(
      padding: const EdgeInsets.fromLTRB(4, 6, 4, 10),
      child: Row(children: [
        Expanded(child: Divider(color: gm.line)),
        Padding(
          padding: const EdgeInsets.symmetric(horizontal: 8),
          child: Text(text, style: GmText.sans(size: 11, color: gm.sub)),
        ),
        Expanded(child: Divider(color: gm.line)),
      ]),
    );
  }
}

class _SlotGrid extends StatelessWidget {
  const _SlotGrid(
      {required this.slug, required this.items, required this.checked});

  final String slug;
  final List<(int, MustSeeItem)> items;
  final Map<String, DateTime> checked;

  @override
  Widget build(BuildContext context) {
    // 三列;Wrap 而不是 GridView:章位下的标题行数不定,不能定高
    return LayoutBuilder(builder: (context, c) {
      final w = c.maxWidth / 3;
      return Wrap(
        runSpacing: 14,
        children: [
          for (final (n, it) in items)
            SizedBox(
              width: w,
              child:
                  _Slot(slug: slug, n: n, item: it, checkedAt: checked[it.qid]),
            ),
        ],
      );
    });
  }
}

class _Slot extends StatelessWidget {
  const _Slot(
      {required this.slug,
      required this.n,
      required this.item,
      required this.checkedAt});

  final String slug;
  final int n;
  final MustSeeItem item;
  final DateTime? checkedAt;

  @override
  Widget build(BuildContext context) {
    final gm = context.gm;
    final l10n = AppLocalizations.of(context)!;
    final ok = checkedAt != null;
    final room = item.location?.room;
    return InkWell(
      onTap: () => context.push('/guide',
          extra: GuideArgs(
            slug: slug,
            qid: item.qid,
            imageUrl: item.thumbnail,
            entry: GuideEntry.collection,
          )),
      child: Column(
        children: [
          SizedBox(
            width: 78,
            height: 78,
            child: ok
                ? Transform.rotate(
                    angle: -8 * math.pi / 180,
                    child: Stack(alignment: Alignment.bottomCenter, children: [
                      Container(
                        decoration: BoxDecoration(
                          shape: BoxShape.circle,
                          border: Border.all(color: gm.accent, width: 3),
                        ),
                        padding: const EdgeInsets.all(2),
                        child: ClipOval(
                          child: SizedBox.expand(
                            child: item.thumbnail == null
                                ? ColoredBox(color: gm.chipBg)
                                : Image.network(
                                    sizedImageUrl(item.thumbnail!, 200),
                                    fit: BoxFit.cover,
                                    cacheWidth: 200,
                                    headers: kImageRequestHeaders,
                                    errorBuilder: (_, __, ___) =>
                                        ColoredBox(color: gm.chipBg),
                                  ),
                          ),
                        ),
                      ),
                      Positioned(
                        bottom: 4,
                        child: Container(
                          padding: const EdgeInsets.symmetric(
                              horizontal: 5, vertical: 1),
                          decoration: BoxDecoration(
                              color: gm.accent,
                              borderRadius: BorderRadius.circular(6)),
                          child: Text(stampDate(checkedAt!),
                              style: GmText.sans(size: 9, color: gm.ctaInk)),
                        ),
                      ),
                    ]),
                  )
                : CustomPaint(
                    painter: _DashedCircle(gm.faint),
                    child: Center(
                      child: Text('$n',
                          style: GmText.serif(size: 20, color: gm.faint)),
                    ),
                  ),
          ),
          const SizedBox(height: 5),
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: 3),
            child: Text(item.title,
                textAlign: TextAlign.center,
                maxLines: 3,
                overflow: TextOverflow.ellipsis,
                style: GmText.sans(
                    size: 11, height: 1.25, color: ok ? gm.ink : gm.sub)),
          ),
          if (room != null)
            Text(l10n.passportRoom(room),
                style: GmText.sans(size: 10, color: gm.sub)),
        ],
      ),
    );
  }
}

/// 完成大章 / 勋章:同一个图案(用户 10-27 选 B「圆形奖章」),只是大小不同。
class _Seal extends StatelessWidget {
  const _Seal(
      {super.key,
      required this.size,
      required this.title,
      required this.count,
      required this.footer});

  final double size;
  final String title;
  final String count;
  final String footer;

  @override
  Widget build(BuildContext context) {
    final gm = context.gm;
    // 章是固定的圆:系统调大字号时整枚章同比放大,不缩字(多语言排版规则)
    final size =
        this.size * MediaQuery.textScalerOf(context).scale(1).clamp(1.0, 1.6);
    final k = size / 200;
    return Transform.rotate(
      angle: -12 * math.pi / 180,
      child: Container(
        width: size,
        height: size,
        decoration: BoxDecoration(
          shape: BoxShape.circle,
          color: gm.surface.withValues(alpha: 0.85),
          border: Border.all(color: gm.accent, width: math.max(2, 5 * k)),
        ),
        padding: EdgeInsets.all(14 * k),
        child: Container(
          decoration: BoxDecoration(
            shape: BoxShape.circle,
            border: Border.all(color: gm.accent, width: math.max(1, 1.5 * k)),
          ),
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              Text(title,
                  textAlign: TextAlign.center,
                  style: GmText.serif(
                      size: math.max(8, 13 * k),
                      color: gm.accent,
                      letterSpacing: 2 * k)),
              Text(count,
                  maxLines: 1,
                  softWrap: false,
                  style: GmText.serif(
                      size: math.max(12, 30 * k),
                      weight: FontWeight.w700,
                      color: gm.accent)),
              Padding(
                padding: EdgeInsets.symmetric(horizontal: 12 * k),
                child: Text(footer,
                    textAlign: TextAlign.center,
                    maxLines: 2,
                    style: GmText.sans(
                        size: math.max(8, 12 * k), color: gm.accent)),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _DashedCircle extends CustomPainter {
  _DashedCircle(this.color);
  final Color color;

  @override
  void paint(Canvas canvas, Size size) {
    final p = Paint()
      ..color = color
      ..style = PaintingStyle.stroke
      ..strokeWidth = 2;
    final r = size.shortestSide / 2 - 1;
    const dashes = 24;
    for (var i = 0; i < dashes; i++) {
      final a = i * 2 * math.pi / dashes;
      canvas.drawArc(
          Rect.fromCircle(center: size.center(Offset.zero), radius: r),
          a,
          math.pi / dashes,
          false,
          p);
    }
  }

  @override
  bool shouldRepaint(_DashedCircle old) => old.color != color;
}
