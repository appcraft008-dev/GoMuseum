import 'package:flutter/material.dart';
import 'package:just_audio/just_audio.dart';

/// 音频播放器组件
///
/// 提供音频播放控制界面，支持播放/暂停、进度条和时间显示。
/// 使用just_audio包处理音频流媒体。
class AudioPlayerWidget extends StatefulWidget {
  /// 音频文件URL（可选）
  final String? audioUrl;

  /// 音频总时长（秒）
  final int? durationSeconds;

  /// 自定义播放器高度
  final double height;

  /// 是否自动播放
  final bool autoPlay;

  const AudioPlayerWidget({
    super.key,
    this.audioUrl,
    this.durationSeconds,
    this.height = 120.0,
    this.autoPlay = false,
  });

  @override
  State<AudioPlayerWidget> createState() => _AudioPlayerWidgetState();
}

class _AudioPlayerWidgetState extends State<AudioPlayerWidget> {
  late final AudioPlayer _audioPlayer;
  bool _isInitialized = false;
  String? _errorMessage;

  @override
  void initState() {
    super.initState();
    _audioPlayer = AudioPlayer();
    _initializePlayer();
  }

  @override
  void dispose() {
    _audioPlayer.dispose();
    super.dispose();
  }

  /// 初始化音频播放器
  Future<void> _initializePlayer() async {
    if (widget.audioUrl == null) {
      return;
    }

    try {
      await _audioPlayer.setUrl(widget.audioUrl!);
      setState(() {
        _isInitialized = true;
        _errorMessage = null;
      });

      if (widget.autoPlay) {
        await _audioPlayer.play();
      }
    } catch (e) {
      setState(() {
        _errorMessage = 'Failed to load audio: ${e.toString()}';
      });
    }
  }

  /// 格式化时长（秒 -> mm:ss）
  String _formatDuration(Duration duration) {
    final minutes = duration.inMinutes.remainder(60).toString().padLeft(2, '0');
    final seconds = duration.inSeconds.remainder(60).toString().padLeft(2, '0');
    return '$minutes:$seconds';
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);

    // 没有音频URL时显示提示
    if (widget.audioUrl == null) {
      return _buildNoAudioPlaceholder(theme);
    }

    // 加载错误时显示错误信息
    if (_errorMessage != null) {
      return _buildErrorPlaceholder(theme, _errorMessage!);
    }

    // 正在初始化时显示加载指示器
    if (!_isInitialized) {
      return _buildLoadingPlaceholder(theme);
    }

    // 正常的播放器界面
    return Container(
      height: widget.height,
      padding: const EdgeInsets.all(16.0),
      decoration: BoxDecoration(
        color: theme.colorScheme.surfaceContainerLow,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(
          color: theme.colorScheme.outlineVariant,
          width: 1,
        ),
      ),
      child: StreamBuilder<PlayerState>(
        stream: _audioPlayer.playerStateStream,
        builder: (context, snapshot) {
          final playerState = snapshot.data;
          final processingState = playerState?.processingState;
          final playing = playerState?.playing ?? false;

          return Column(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              // 播放控制按钮
              Row(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  // 播放/暂停按钮
                  IconButton(
                    icon: Icon(
                      playing
                          ? Icons.pause_circle_filled
                          : Icons.play_circle_filled,
                      size: 48,
                    ),
                    color: theme.colorScheme.primary,
                    onPressed: () {
                      if (playing) {
                        _audioPlayer.pause();
                      } else {
                        _audioPlayer.play();
                      }
                    },
                  ),

                  const SizedBox(width: 16),

                  // 停止按钮
                  IconButton(
                    icon: const Icon(Icons.stop_circle_outlined, size: 36),
                    color: theme.colorScheme.secondary,
                    onPressed: () async {
                      await _audioPlayer.stop();
                      await _audioPlayer.seek(Duration.zero);
                    },
                  ),
                ],
              ),

              const SizedBox(height: 12),

              // 进度条和时间显示
              StreamBuilder<Duration?>(
                stream: _audioPlayer.positionStream,
                builder: (context, snapshot) {
                  final position = snapshot.data ?? Duration.zero;
                  final duration = _audioPlayer.duration ?? Duration.zero;

                  return Column(
                    children: [
                      // 进度条
                      SliderTheme(
                        data: SliderTheme.of(context).copyWith(
                          trackHeight: 4.0,
                          thumbShape: const RoundSliderThumbShape(
                            enabledThumbRadius: 6.0,
                          ),
                        ),
                        child: Slider(
                          value: position.inSeconds.toDouble(),
                          max: duration.inSeconds
                              .toDouble()
                              .clamp(0.0, double.infinity),
                          onChanged: (value) {
                            _audioPlayer.seek(Duration(seconds: value.toInt()));
                          },
                        ),
                      ),

                      // 时间显示
                      Padding(
                        padding: const EdgeInsets.symmetric(horizontal: 16.0),
                        child: Row(
                          mainAxisAlignment: MainAxisAlignment.spaceBetween,
                          children: [
                            Text(
                              _formatDuration(position),
                              style: theme.textTheme.bodySmall?.copyWith(
                                color: theme.colorScheme.onSurfaceVariant,
                              ),
                            ),
                            Text(
                              _formatDuration(duration),
                              style: theme.textTheme.bodySmall?.copyWith(
                                color: theme.colorScheme.onSurfaceVariant,
                              ),
                            ),
                          ],
                        ),
                      ),
                    ],
                  );
                },
              ),

              // 加载状态指示器
              if (processingState == ProcessingState.loading ||
                  processingState == ProcessingState.buffering)
                const Padding(
                  padding: EdgeInsets.only(top: 8.0),
                  child: LinearProgressIndicator(),
                ),
            ],
          );
        },
      ),
    );
  }

  /// 构建无音频占位符
  Widget _buildNoAudioPlaceholder(ThemeData theme) {
    return Container(
      height: widget.height,
      padding: const EdgeInsets.all(16.0),
      decoration: BoxDecoration(
        color: theme.colorScheme.surfaceContainerLow,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(
          color: theme.colorScheme.outlineVariant,
          width: 1,
        ),
      ),
      child: Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(
              Icons.volume_off,
              size: 48,
              color: theme.colorScheme.onSurfaceVariant,
            ),
            const SizedBox(height: 8),
            Text(
              'No audio available',
              style: theme.textTheme.bodyMedium?.copyWith(
                color: theme.colorScheme.onSurfaceVariant,
              ),
            ),
          ],
        ),
      ),
    );
  }

  /// 构建错误占位符
  Widget _buildErrorPlaceholder(ThemeData theme, String error) {
    return Container(
      height: widget.height,
      padding: const EdgeInsets.all(16.0),
      decoration: BoxDecoration(
        color: theme.colorScheme.errorContainer,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(
          color: theme.colorScheme.error,
          width: 1,
        ),
      ),
      child: Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(
              Icons.error_outline,
              size: 48,
              color: theme.colorScheme.onErrorContainer,
            ),
            const SizedBox(height: 8),
            Text(
              error,
              textAlign: TextAlign.center,
              style: theme.textTheme.bodySmall?.copyWith(
                color: theme.colorScheme.onErrorContainer,
              ),
            ),
          ],
        ),
      ),
    );
  }

  /// 构建加载占位符
  Widget _buildLoadingPlaceholder(ThemeData theme) {
    return Container(
      height: widget.height,
      padding: const EdgeInsets.all(16.0),
      decoration: BoxDecoration(
        color: theme.colorScheme.surfaceContainerLow,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(
          color: theme.colorScheme.outlineVariant,
          width: 1,
        ),
      ),
      child: Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            CircularProgressIndicator(
              color: theme.colorScheme.primary,
            ),
            const SizedBox(height: 16),
            Text(
              'Loading audio...',
              style: theme.textTheme.bodyMedium?.copyWith(
                color: theme.colorScheme.onSurfaceVariant,
              ),
            ),
          ],
        ),
      ),
    );
  }
}
