// 完播率埋点(V78)的上报状态机。钉的是会报重、报漏的几处:
// 暂停后续播是同一次收听;播完后重听是新的一次;没在播就不报。
import 'package:flutter_test/flutter_test.dart';
import 'package:gomuseum_app/features/guide/data/content_viewed.dart';
import 'package:gomuseum_app/features/guide/data/listen_tracker.dart';

void main() {
  late List<(ListenEnd, Duration, String)> sent;
  late ListenTracker t;
  setUp(() {
    sent = [];
    t = ListenTracker(
      (end, played, _, session) => sent.add((end, played, session)),
    );
  });

  test('没开播就结束 → 不报', () {
    t.end(ListenEnd.exit, Duration.zero, null);
    expect(sent, isEmpty);
  });

  test('暂停只报一次;续播再暂停是同一个 session', () {
    t.onPlaying();
    t.onPlaying(); // 缓冲时 playing 事件会重复来
    t.end(ListenEnd.pause, const Duration(seconds: 10), null);
    t.end(ListenEnd.pause, const Duration(seconds: 10), null);
    t.onPlaying();
    t.end(ListenEnd.exit, const Duration(seconds: 30), null);
    expect(sent.map((e) => e.$1), [ListenEnd.pause, ListenEnd.exit]);
    expect(sent[0].$3, sent[1].$3);
    expect(sent[1].$2, const Duration(seconds: 30));
  });

  test('播完后重听 → 新 session', () {
    t.onPlaying();
    t.end(ListenEnd.complete, const Duration(seconds: 90), null);
    t.onPlaying();
    t.end(ListenEnd.pause, const Duration(seconds: 5), null);
    expect(sent[0].$3, isNot(sent[1].$3));
  });

  test('换源后 → 新 session', () {
    t.onPlaying();
    t.end(ListenEnd.switch_, const Duration(seconds: 3), null);
    t.reset();
    t.onPlaying();
    t.end(ListenEnd.pause, const Duration(seconds: 4), null);
    expect(sent[0].$3, isNot(sent[1].$3));
  });

  test('另一段接班:先报 switch,随后状态流来的 pause 不再重报', () {
    // GuideAudioPlayer._pauseQuiet 依赖这条:先 end(switch_) 再 pause()
    t.onPlaying();
    t.end(ListenEnd.switch_, const Duration(seconds: 12), null);
    t.end(ListenEnd.pause, const Duration(seconds: 12), null);
    expect(sent.map((e) => e.$1), [ListenEnd.switch_]);
  });
}
