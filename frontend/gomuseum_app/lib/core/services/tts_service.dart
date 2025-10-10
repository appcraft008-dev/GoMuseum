import 'package:just_audio/just_audio.dart';
import 'package:flutter/foundation.dart';

/// TTS音频服务
class TtsService {
  final AudioPlayer _audioPlayer = AudioPlayer();

  /// 播放状态流
  Stream<PlayerState> get playerStateStream => _audioPlayer.playerStateStream;

  /// 当前播放位置
  Stream<Duration> get positionStream => _audioPlayer.positionStream;

  /// 音频总时长
  Stream<Duration?> get durationStream => _audioPlayer.durationStream;

  /// 是否正在播放
  bool get isPlaying => _audioPlayer.playing;

  /// 播放TTS音频
  ///
  /// [url] - 音频URL（后端TTS生成的音频地址）
  Future<void> play(String url) async {
    try {
      await _audioPlayer.setUrl(url);
      await _audioPlayer.play();
    } catch (e) {
      debugPrint('TTS播放失败: $e');
      rethrow;
    }
  }

  /// 暂停播放
  Future<void> pause() async {
    await _audioPlayer.pause();
  }

  /// 继续播放
  Future<void> resume() async {
    await _audioPlayer.play();
  }

  /// 停止播放
  Future<void> stop() async {
    await _audioPlayer.stop();
  }

  /// 跳转到指定位置
  Future<void> seek(Duration position) async {
    await _audioPlayer.seek(position);
  }

  /// 设置播放速度
  Future<void> setSpeed(double speed) async {
    await _audioPlayer.setSpeed(speed);
  }

  /// 释放资源
  Future<void> dispose() async {
    await _audioPlayer.dispose();
  }
}
