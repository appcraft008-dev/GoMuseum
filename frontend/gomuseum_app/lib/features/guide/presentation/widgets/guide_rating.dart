import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'package:gomuseum_app/features/auth/presentation/auth_provider.dart'
    show dioProvider;
import 'package:gomuseum_app/features/feedback/presentation/widgets/feedback_sheet.dart';
import 'package:gomuseum_app/features/guide/data/content_viewed.dart';
import 'package:gomuseum_app/l10n/app_localizations.dart';
import 'package:gomuseum_app/theme/gm_theme_x.dart';
import 'package:gomuseum_app/ui/gm/gm.dart';

/// 主讲解末尾「这段讲解对你有帮助吗? 👍 👎」(V78,10-31 用户定)。
///
/// 放在末尾而不是顶栏:刚进页面还没听没读,没东西可评。
/// 👍 只说谢谢 —— 夸的理由很少能拿来改东西,多问一步反而劝退;
/// 👎 先记一次,再弹反馈面板(可以不填直接关,这次不满意也已经记下了)。
/// 选择按件×语言记在本机:点同一个不重复报,改主意再报一条。
class GuideRating extends ConsumerStatefulWidget {
  const GuideRating({
    super.key,
    required this.slug,
    required this.qid,
    required this.language,
  });

  final String slug;
  final String qid;

  /// API 语言参数:10 语是 10 份独立内容,评价跟着语言走。
  final String language;

  @override
  ConsumerState<GuideRating> createState() => _GuideRatingState();
}

class _GuideRatingState extends ConsumerState<GuideRating> {
  bool? _up; // null = 还没评

  String get _key => 'guide_rating:${widget.qid}:${widget.language}';

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    try {
      final v = (await SharedPreferences.getInstance()).getString(_key);
      if (mounted && v != null) setState(() => _up = v == 'up');
    } catch (_) {}
  }

  Future<void> _rate(bool up) async {
    if (_up == up) return;
    setState(() => _up = up);
    unawaited(reportContentRated(ref.read(dioProvider),
        slug: widget.slug, qid: widget.qid, language: widget.language, up: up));
    try {
      await (await SharedPreferences.getInstance())
          .setString(_key, up ? 'up' : 'down');
    } catch (_) {}
    if (!mounted) return;
    if (up) {
      ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text(AppLocalizations.of(context)!.fbThanks)));
    } else {
      await showFeedbackSheet(context,
          slug: widget.slug, qid: widget.qid, language: widget.language);
    }
  }

  @override
  Widget build(BuildContext context) {
    final gm = context.gm;
    final l10n = AppLocalizations.of(context)!;
    Widget button(bool up) {
      final on = _up == up;
      return Semantics(
        button: true,
        selected: on,
        label: up ? l10n.guideRateUp : l10n.guideRateDown,
        excludeSemantics: true,
        child: GestureDetector(
          onTap: () => _rate(up),
          behavior: HitTestBehavior.opaque,
          child: Padding(
            padding: const EdgeInsets.all(8),
            child: GmIcon(up ? GmIcons.thumbUp : GmIcons.thumbDown,
                size: 20, color: on ? gm.accent : gm.sub, fill: on),
          ),
        ),
      );
    }

    return Padding(
      padding: const EdgeInsets.only(top: 16),
      child: Row(children: [
        Expanded(
          child: Text(l10n.guideRateQuestion,
              style: GmText.sans(size: 12.5, color: gm.sub)),
        ),
        button(true),
        button(false),
      ]),
    );
  }
}
