import 'dart:async';

import 'package:flutter_test/flutter_test.dart';
import 'package:gomuseum_app/features/guide/presentation/widgets/tts_chunk_audio_source.dart';

/// 读一个 request() 响应的全部字节。
Future<List<int>> _drain(TtsChunkAudioSource s, {int? start, int? end}) async {
  final rsp = await s.request(start, end);
  final out = <int>[];
  await for (final c in rsp.stream) {
    out.addAll(c);
  }
  return out;
}

void main() {
  test('渐进：先 request 后到达的 chunk 也能按序读全（不丢/不乱序）', () async {
    final ctl = StreamController<List<int>>();
    final src = TtsChunkAudioSource(ctl.stream);

    // 请求先发起（此时缓冲为空），消费在后台等待新数据。
    final drained = _drain(src);

    ctl.add([1, 2, 3]);
    await Future<void>.delayed(Duration.zero);
    ctl.add([4, 5]);
    await Future<void>.delayed(Duration.zero);
    ctl.add([6, 7, 8, 9]);
    await ctl.close();

    expect(await drained, [1, 2, 3, 4, 5, 6, 7, 8, 9]);
  });

  test('已缓冲后再 request：立即读全', () async {
    final ctl = StreamController<List<int>>();
    final src = TtsChunkAudioSource(ctl.stream);
    ctl.add([10, 20, 30]);
    await ctl.close();
    await Future<void>.delayed(Duration.zero);

    expect(await _drain(src), [10, 20, 30]);
  });

  test('带 start/end：只吐该区间字节', () async {
    final ctl = StreamController<List<int>>();
    final src = TtsChunkAudioSource(ctl.stream);
    ctl.add([0, 1, 2, 3, 4, 5, 6, 7]);
    await ctl.close();
    await Future<void>.delayed(Duration.zero);

    expect(await _drain(src, start: 2, end: 5), [2, 3, 4]); // [start,end)
  });

  test('首读预缓冲：达阈值前 request 挂起，越过阈值才返回', () async {
    final ctl = StreamController<List<int>>();
    final src = TtsChunkAudioSource(ctl.stream);
    var resolved = false;
    // ignore: unawaited_futures
    src.request(0).then((_) => resolved = true);

    ctl.add(List.filled(20000, 1)); // < 32KB 阈值
    await Future<void>.delayed(Duration.zero);
    expect(resolved, isFalse, reason: '未达 32KB 前 request 应仍挂起');

    ctl.add(List.filled(20000, 2)); // 累计 40000 > 32768
    await Future<void>.delayed(Duration.zero);
    expect(resolved, isTrue, reason: '越过阈值后 request 应返回');
  });

  test('首读预缓冲：源提前结束(不足阈值)也返回，不挂死', () async {
    final ctl = StreamController<List<int>>();
    final src = TtsChunkAudioSource(ctl.stream);
    ctl.add(List.filled(100, 9)); // 远小于阈值
    await ctl.close(); // done
    final rsp = await src.request(0).timeout(const Duration(seconds: 1));
    expect(rsp.contentType, 'audio/mpeg');
  });

  test('源报错：已到字节读完后抛出错误', () async {
    final ctl = StreamController<List<int>>();
    final src = TtsChunkAudioSource(ctl.stream);
    final drained = _drain(src);
    ctl.add([1, 2]);
    await Future<void>.delayed(Duration.zero);
    ctl.addError(StateError('boom'));

    await expectLater(drained, throwsA(isA<StateError>()));
  });
}
