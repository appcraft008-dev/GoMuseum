import 'package:flutter/material.dart';
import 'package:just_audio/just_audio.dart';

/// 简单的音频播放器控制组件
class AudioPlayerWidget extends StatefulWidget {
  final AudioPlayer audioPlayer;
  final VoidCallback? onPlay;
  final VoidCallback? onPause;
  final VoidCallback? onStop;

  const AudioPlayerWidget({
    super.key,
    required this.audioPlayer,
    this.onPlay,
    this.onPause,
    this.onStop,
  });

  @override
  State<AudioPlayerWidget> createState() => _AudioPlayerWidgetState();
}

class _AudioPlayerWidgetState extends State<AudioPlayerWidget> {
  Duration _position = Duration.zero;
  Duration _duration = Duration.zero;
  bool _isPlaying = false;

  @override
  void initState() {
    super.initState();
    _setupListeners();
  }

  void _setupListeners() {
    // 监听播放状态
    widget.audioPlayer.playerStateStream.listen((state) {
      if (mounted) {
        setState(() {
          _isPlaying = state.playing;
        });
      }
    });

    // 监听播放位置
    widget.audioPlayer.positionStream.listen((position) {
      if (mounted) {
        setState(() {
          _position = position;
        });
      }
    });

    // 监听总时长
    widget.audioPlayer.durationStream.listen((duration) {
      if (mounted && duration != null) {
        setState(() {
          _duration = duration;
        });
      }
    });
  }

  @override
  Widget build(BuildContext context) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            // 播放/暂停按钮
            Row(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                IconButton(
                  icon: Icon(_isPlaying ? Icons.pause : Icons.play_arrow),
                  iconSize: 48,
                  onPressed: _handlePlayPause,
                ),
                const SizedBox(width: 16),
                IconButton(
                  icon: const Icon(Icons.stop),
                  iconSize: 48,
                  onPressed: _handleStop,
                ),
              ],
            ),

            const SizedBox(height: 16),

            // 进度条
            Column(
              children: [
                Slider(
                  value: _position.inMilliseconds.toDouble(),
                  max: _duration.inMilliseconds.toDouble() > 0
                      ? _duration.inMilliseconds.toDouble()
                      : 1.0,
                  onChanged: _handleSeek,
                ),
                Padding(
                  padding: const EdgeInsets.symmetric(horizontal: 16),
                  child: Row(
                    mainAxisAlignment: MainAxisAlignment.spaceBetween,
                    children: [
                      Text(_formatDuration(_position)),
                      Text(_formatDuration(_duration)),
                    ],
                  ),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }

  void _handlePlayPause() async {
    if (_isPlaying) {
      await widget.audioPlayer.pause();
      widget.onPause?.call();
    } else {
      await widget.audioPlayer.play();
      widget.onPlay?.call();
    }
  }

  void _handleStop() async {
    await widget.audioPlayer.stop();
    widget.onStop?.call();
  }

  void _handleSeek(double value) {
    widget.audioPlayer.seek(Duration(milliseconds: value.toInt()));
  }

  String _formatDuration(Duration duration) {
    String twoDigits(int n) => n.toString().padLeft(2, '0');
    final minutes = twoDigits(duration.inMinutes.remainder(60));
    final seconds = twoDigits(duration.inSeconds.remainder(60));
    return '$minutes:$seconds';
  }
}
