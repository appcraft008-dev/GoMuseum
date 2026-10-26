/// 系统播放卡片跟着「当前在放的那段」走(见 media_session.dart)。
///
/// 讲解页一段一个播放器,切 tab / 展开问答时旧段的 State 会被释放;
/// 最容易出错的是:**卡片已被新段接走,旧段释放时把新段的卡片清掉了**。
import 'package:audio_service/audio_service.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gomuseum_app/core/services/media_session.dart';
import 'package:just_audio/just_audio.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  late GuideMediaHandler h;
  late AudioPlayer a;
  late AudioPlayer b;
  setUp(() {
    h = GuideMediaHandler();
    a = AudioPlayer(handleInterruptions: false);
    b = AudioPlayer(handleInterruptions: false);
  });
  tearDown(() async {
    await a.dispose();
    await b.dispose();
  });

  const itemA = MediaItem(id: 'A', title: '蒙娜丽莎', artist: '达·芬奇 · 卢浮宫');
  const itemB = MediaItem(id: 'B', title: '蒙娜丽莎', artist: '创作背景');

  test('开播 → 卡片出现;释放 → 卡片消失', () {
    h.attach(a, itemA);
    expect(h.mediaItem.value?.title, '蒙娜丽莎');
    expect(h.mediaItem.value?.artist, '达·芬奇 · 卢浮宫');

    h.detach(a);
    expect(h.mediaItem.value, isNull);
    expect(h.playbackState.value.playing, isFalse);
  });

  test('⭐ 新段接班后旧段释放 → 卡片仍是新段的', () {
    h.attach(a, itemA);
    h.attach(b, itemB);
    h.detach(a); // 旧段的 State 被释放
    expect(h.mediaItem.value?.id, 'B');
  });

  test('没加载音频(总时长未知)→ 只有播放键,不给拖进度', () {
    h.attach(a, itemA);
    final s = h.playbackState.value;
    expect(s.controls, [MediaControl.play]);
    expect(s.systemActions, isNot(contains(MediaAction.seek)));
    expect(s.systemActions, contains(MediaAction.playPause)); // 耳机键
  });

  test('没有在放的段时,锁屏按键是空操作(不抛错)', () async {
    await h.play();
    await h.pause();
    await h.seek(Duration.zero);
    await h.stop();
  });
}
