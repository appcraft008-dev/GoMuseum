/// 渐进播放源：把 HTTP chunk 流边到边喂给 just_audio(ExoPlayer)，首个 chunk 到即出声。
/// 流式响应无 Content-Length、不支持 Range/seek（rangeRequestsSupported=false）；
/// 整段播完或下次走 R2 直链时恢复全功能。字节顺序/完整性靠单缓冲 + 位点游标保证。
library;

// StreamAudioSource/Response 是 just_audio 标注 experimental 的正式渐进播放 API（预期用法）。
// ignore_for_file: experimental_member_use

import 'dart:async';

import 'package:just_audio/just_audio.dart';

class TtsChunkAudioSource extends StreamAudioSource {
  TtsChunkAudioSource(Stream<List<int>> input) {
    _sub = input.listen(
      (chunk) {
        _buffer.addAll(chunk);
        _wake();
      },
      onDone: () {
        _done = true;
        _wake();
      },
      onError: (Object e, StackTrace _) {
        _error = e;
        _done = true;
        _wake();
      },
      cancelOnError: true,
    );
  }

  final List<int> _buffer = [];
  bool _done = false;
  Object? _error;
  StreamSubscription<List<int>>? _sub;
  final List<Completer<void>> _waiters = [];

  void _wake() {
    final ws = List.of(_waiters);
    _waiters.clear();
    for (final c in ws) {
      if (!c.isCompleted) c.complete();
    }
  }

  @override
  Future<StreamAudioResponse> request([int? start, int? end]) async {
    final from = start ?? 0;
    return StreamAudioResponse(
      rangeRequestsSupported: false,
      sourceLength: null, // 流式总长未知
      contentLength: null,
      offset: from,
      contentType: 'audio/mpeg',
      stream: _emit(from, end),
    );
  }

  /// 已缓冲部分立即吐出，之后随新 chunk 到达继续吐，直到源结束。
  Stream<List<int>> _emit(int from, int? end) async* {
    var pos = from;
    while (true) {
      if (pos < _buffer.length) {
        final upto = end == null
            ? _buffer.length
            : (end < _buffer.length ? end : _buffer.length);
        if (pos < upto) {
          yield _buffer.sublist(pos, upto);
          pos = upto;
        }
      }
      if (end != null && pos >= end) return;
      if (_done) {
        if (_error != null && pos >= _buffer.length) throw _error!;
        return;
      }
      final c = Completer<void>();
      _waiters.add(c);
      await c.future;
    }
  }

  void dispose() {
    _sub?.cancel();
    _sub = null;
    _wake();
  }
}
