/// 系统媒体会话:iOS 锁屏/控制中心、Android 锁屏/通知栏的播放卡片 + 耳机/蓝牙按键。
///
/// 讲解页每段各有一个 [AudioPlayer](见 guide_audio_player.dart 的 `_ActiveAudio`,
/// 同时只放一段),所以这里不持有播放器:哪段开播就 [MediaSession.attach] 哪段,
/// 系统按键转给它;播放器释放时 [MediaSession.detach],卡片随之消失。
/// just_audio_background 只支持全 App 一个播放器,套不上这个结构,所以直接用 audio_service。
library;

import 'dart:async';

import 'package:audio_service/audio_service.dart';
import 'package:flutter/foundation.dart';
import 'package:just_audio/just_audio.dart';

class MediaSession {
  MediaSession._();

  /// null = 没初始化成功(单测、或系统不给起服务)。调用方一律可空调用,卡片缺席不影响播放。
  static GuideMediaHandler? _handler;

  static Future<void> init() async {
    try {
      _handler = await AudioService.init(
        builder: GuideMediaHandler.new,
        config: const AudioServiceConfig(
          androidNotificationChannelId: 'com.gomuseum.app.audio',
          androidNotificationChannelName: 'Audio guide',
          // 暂停时撤掉前台服务、通知可划掉;播放中常驻
          androidNotificationOngoing: true,
          androidStopForegroundOnPause: true,
        ),
      );
    } catch (e) {
      debugPrint('MediaSession init failed: $e');
    }
  }

  static void attach(AudioPlayer player, MediaItem item) =>
      _handler?.attach(player, item);

  static void detach(AudioPlayer player) => _handler?.detach(player);
}

@visibleForTesting
class GuideMediaHandler extends BaseAudioHandler with SeekHandler {
  AudioPlayer? _player;
  final List<StreamSubscription<Object?>> _subs = [];

  void attach(AudioPlayer player, MediaItem item) {
    if (!identical(player, _player)) {
      _cancel();
      _player = player;
      _subs
        ..add(player.playbackEventStream.listen((_) => _broadcast()))
        ..add(player.playingStream.listen((_) => _broadcast()))
        // 流式音频起播时不知道总时长,拿到后补上,系统进度条才出来
        ..add(player.durationStream.listen((d) {
          final cur = mediaItem.value;
          if (cur != null && d != null) {
            mediaItem.add(cur.copyWith(duration: d));
          }
        }));
    }
    mediaItem.add(item.copyWith(duration: player.duration));
    _broadcast();
  }

  void detach(AudioPlayer player) {
    if (!identical(player, _player)) return; // 已被别的段接走,别把它的卡片清掉
    _cancel();
    _player = null;
    mediaItem.add(null);
    playbackState.add(PlaybackState());
  }

  void _cancel() {
    for (final s in _subs) {
      s.cancel();
    }
    _subs.clear();
  }

  void _broadcast() {
    final p = _player;
    if (p == null) return;
    playbackState.add(playbackState.value.copyWith(
      controls: [p.playing ? MediaControl.pause : MediaControl.play],
      androidCompactActionIndices: const [0],
      // 流式无总时长时不能 seek(同 App 内进度条的规则)
      systemActions: {
        // 耳机线控/AirPods 单击发的是 playPause,不声明 iOS 上会禁用该命令
        MediaAction.playPause,
        if (p.duration != null) MediaAction.seek,
      },
      processingState: const {
        ProcessingState.idle: AudioProcessingState.idle,
        ProcessingState.loading: AudioProcessingState.loading,
        ProcessingState.buffering: AudioProcessingState.buffering,
        ProcessingState.ready: AudioProcessingState.ready,
        ProcessingState.completed: AudioProcessingState.completed,
      }[p.processingState]!,
      playing: p.playing,
      updatePosition: p.position,
      bufferedPosition: p.bufferedPosition,
      speed: p.speed,
    ));
  }

  @override
  Future<void> play() async {
    final p = _player;
    if (p == null) return;
    if (p.processingState == ProcessingState.completed) {
      await p.seek(Duration.zero); // 同 App 内:播完再按播放 = 从头
    }
    unawaited(p.play()); // just_audio 的 play() 要等到停播才返回
  }

  @override
  Future<void> pause() async => _player?.pause();

  @override
  Future<void> seek(Duration position) async => _player?.seek(position);

  @override
  Future<void> stop() async => _player?.pause();
}
