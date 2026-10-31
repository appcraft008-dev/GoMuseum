import 'dart:math';

import 'package:gomuseum_app/features/guide/data/content_viewed.dart';

typedef ListenSend = void Function(
    ListenEnd end, Duration played, Duration? duration, String session);

/// 一次收听的上报状态机(V78 完播率)。从播放器里抽出来便于单测。
///
/// 开播后第一次「结束」(暂停/播完/切走/退出)才报,重复的结束事件不重报;
/// 暂停→续播仍是同一个 session(分析时按 session 取最大播放位置);
/// 播完或换源后再播 = 新的一次收听。
class ListenTracker {
  ListenTracker(this._send);

  final ListenSend _send;
  String? _session;
  bool _open = false;

  void onPlaying() {
    _session ??= _newId();
    _open = true;
  }

  void end(ListenEnd e, Duration played, Duration? duration) {
    if (!_open) return;
    _open = false;
    _send(e, played, duration, _session!);
    if (e == ListenEnd.complete) _session = null;
  }

  void reset() {
    _session = null;
    _open = false;
  }

  static final _rand = Random();
  // ponytail: 不引 uuid 包,时间+随机数足够区分同一台设备上的收听
  static String _newId() =>
      '${DateTime.now().microsecondsSinceEpoch.toRadixString(36)}'
      '${_rand.nextInt(1 << 32).toRadixString(36)}';
}
