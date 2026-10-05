import 'dart:async';

import 'package:flutter/widgets.dart';
import 'package:gomuseum_app/l10n/app_localizations.dart';

/// 识别等待中的说明行,随等待时长换文案(S2 ⑪):
/// 0s 现文案 → 10s「还在找」→ 20s「可以先切到其他应用」。
/// 只承诺「切到其他应用」,不承诺离开页面(用户 2026-10-05:说「离开」分不清是页面还是 App)。
/// 重发期间识别状态一直是 Loading,本组件不重建,计时连续。
class RecognitionWaitHint extends StatefulWidget {
  const RecognitionWaitHint({super.key, required this.style});
  final TextStyle style;

  @override
  State<RecognitionWaitHint> createState() => _RecognitionWaitHintState();
}

class _RecognitionWaitHintState extends State<RecognitionWaitHint> {
  int _stage = 0;
  late final List<Timer> _timers;

  @override
  void initState() {
    super.initState();
    _timers = [
      Timer(const Duration(seconds: 10), () => setState(() => _stage = 1)),
      Timer(const Duration(seconds: 20), () => setState(() => _stage = 2)),
    ];
  }

  @override
  void dispose() {
    for (final t in _timers) {
      t.cancel();
    }
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context)!;
    final text = switch (_stage) {
      0 => l10n.camComparing,
      1 => l10n.recWaitSlow,
      _ => l10n.recWaitSwitchApp,
    };
    return Text(text, style: widget.style);
  }
}
