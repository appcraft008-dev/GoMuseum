# Content Module Usage Examples

## Overview

Content模块提供艺术品讲解生成和TTS音频生成功能，遵循Clean Architecture模式。

## Directory Structure

```
lib/features/content/
├── domain/
│   ├── entities/
│   │   └── explanation.dart              # 讲解实体
│   ├── repositories/
│   │   └── content_repository.dart       # Repository接口
│   └── usecases/
│       ├── generate_explanation.dart     # 生成讲解UseCase
│       └── generate_tts_audio.dart       # 生成TTS音频UseCase
├── data/
│   ├── models/
│   │   └── explanation_model.dart        # 讲解Model (JSON序列化)
│   ├── datasources/
│   │   └── content_remote_datasource.dart # 远程数据源
│   └── repositories/
│       └── content_repository_impl.dart   # Repository实现
└── presentation/
    ├── providers/
    │   ├── content_providers.dart         # Riverpod Providers
    │   └── content_providers.g.dart       # 生成的Provider代码
    └── widgets/
        ├── explanation_card.dart          # 讲解卡片组件
        └── audio_player_widget.dart       # 音频播放器组件
```

## Usage Examples

### 1. 生成艺术品讲解

```dart
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:gomuseum_app/features/content/domain/usecases/generate_explanation.dart';
import 'package:gomuseum_app/features/content/presentation/providers/content_providers.dart';
import 'package:gomuseum_app/features/content/presentation/widgets/explanation_card.dart';

class ArtworkDetailPage extends ConsumerWidget {
  final String artworkName;
  final String artist;
  final String period;

  const ArtworkDetailPage({
    super.key,
    required this.artworkName,
    required this.artist,
    required this.period,
  });

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    return Scaffold(
      appBar: AppBar(title: Text(artworkName)),
      body: Center(
        child: ElevatedButton(
          onPressed: () async {
            // 获取UseCase
            final useCase = ref.read(generateExplanationUseCaseProvider);

            // 创建参数
            final params = GenerateExplanationParams(
              artworkName: artworkName,
              artist: artist,
              period: period,
              language: 'en', // 或 'zh', 'ja' 等
              description: '可选的额外描述',
            );

            // 调用UseCase
            final result = await useCase(params);

            // 处理结果
            result.fold(
              (failure) {
                // 处理错误
                ScaffoldMessenger.of(context).showSnackBar(
                  SnackBar(content: Text('Error: ${failure.message}')),
                );
              },
              (explanation) {
                // 显示讲解
                showDialog(
                  context: context,
                  builder: (context) => Dialog(
                    child: ExplanationCard(explanation: explanation),
                  ),
                );
              },
            );
          },
          child: const Text('生成讲解'),
        ),
      ),
    );
  }
}
```

### 2. 生成并播放TTS音频

```dart
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:just_audio/just_audio.dart';
import 'package:gomuseum_app/features/content/domain/usecases/generate_tts_audio.dart';
import 'package:gomuseum_app/features/content/presentation/providers/content_providers.dart';
import 'package:gomuseum_app/features/content/presentation/widgets/audio_player_widget.dart';

class TtsAudioExample extends ConsumerStatefulWidget {
  final String text;

  const TtsAudioExample({
    super.key,
    required this.text,
  });

  @override
  ConsumerState<TtsAudioExample> createState() => _TtsAudioExampleState();
}

class _TtsAudioExampleState extends ConsumerState<TtsAudioExample> {
  final AudioPlayer _audioPlayer = AudioPlayer();
  bool _isLoading = false;

  @override
  void dispose() {
    _audioPlayer.dispose();
    super.dispose();
  }

  Future<void> _generateAndPlayAudio() async {
    setState(() => _isLoading = true);

    try {
      // 获取UseCase
      final useCase = ref.read(generateTtsAudioUseCaseProvider);

      // 创建参数
      final params = GenerateTtsAudioParams(
        text: widget.text,
        language: 'en',
        speed: 1.0, // 可选：播放速度 (0.5 - 2.0)
      );

      // 调用UseCase
      final result = await useCase(params);

      // 处理结果
      await result.fold(
        (failure) async {
          // 处理错误
          if (mounted) {
            ScaffoldMessenger.of(context).showSnackBar(
              SnackBar(content: Text('Error: ${failure.message}')),
            );
          }
        },
        (audioUrl) async {
          // 播放音频
          await _audioPlayer.setUrl(audioUrl);
          await _audioPlayer.play();
        },
      );
    } finally {
      if (mounted) {
        setState(() => _isLoading = false);
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('TTS Audio')),
      body: Column(
        children: [
          if (_isLoading)
            const CircularProgressIndicator()
          else
            ElevatedButton(
              onPressed: _generateAndPlayAudio,
              child: const Text('生成并播放音频'),
            ),
          const SizedBox(height: 20),
          AudioPlayerWidget(audioPlayer: _audioPlayer),
        ],
      ),
    );
  }
}
```

### 3. 在ExplanationPage中集成

```dart
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:just_audio/just_audio.dart';
import 'package:gomuseum_app/features/content/domain/entities/explanation.dart';
import 'package:gomuseum_app/features/content/domain/usecases/generate_explanation.dart';
import 'package:gomuseum_app/features/content/domain/usecases/generate_tts_audio.dart';
import 'package:gomuseum_app/features/content/presentation/providers/content_providers.dart';
import 'package:gomuseum_app/features/content/presentation/widgets/explanation_card.dart';
import 'package:gomuseum_app/features/content/presentation/widgets/audio_player_widget.dart';

class IntegratedExplanationPage extends ConsumerStatefulWidget {
  final String artworkName;
  final String artist;
  final String period;

  const IntegratedExplanationPage({
    super.key,
    required this.artworkName,
    required this.artist,
    required this.period,
  });

  @override
  ConsumerState<IntegratedExplanationPage> createState() =>
      _IntegratedExplanationPageState();
}

class _IntegratedExplanationPageState
    extends ConsumerState<IntegratedExplanationPage> {
  final AudioPlayer _audioPlayer = AudioPlayer();
  Explanation? _explanation;
  bool _isLoadingExplanation = false;
  bool _isLoadingAudio = false;

  @override
  void initState() {
    super.initState();
    _loadExplanation();
  }

  @override
  void dispose() {
    _audioPlayer.dispose();
    super.dispose();
  }

  Future<void> _loadExplanation() async {
    setState(() => _isLoadingExplanation = true);

    final useCase = ref.read(generateExplanationUseCaseProvider);
    final params = GenerateExplanationParams(
      artworkName: widget.artworkName,
      artist: widget.artist,
      period: widget.period,
      language: 'en',
    );

    final result = await useCase(params);
    result.fold(
      (failure) {
        if (mounted) {
          ScaffoldMessenger.of(context).showSnackBar(
            SnackBar(content: Text('Failed to load explanation: ${failure.message}')),
          );
        }
      },
      (explanation) {
        if (mounted) {
          setState(() => _explanation = explanation);
        }
      },
    );

    if (mounted) {
      setState(() => _isLoadingExplanation = false);
    }
  }

  Future<void> _playAudio() async {
    if (_explanation == null) return;

    setState(() => _isLoadingAudio = true);

    final useCase = ref.read(generateTtsAudioUseCaseProvider);
    final params = GenerateTtsAudioParams(
      text: _explanation!.summary,
      language: _explanation!.language,
    );

    final result = await useCase(params);
    await result.fold(
      (failure) async {
        if (mounted) {
          ScaffoldMessenger.of(context).showSnackBar(
            SnackBar(content: Text('Failed to generate audio: ${failure.message}')),
          );
        }
      },
      (audioUrl) async {
        await _audioPlayer.setUrl(audioUrl);
        await _audioPlayer.play();
      },
    );

    if (mounted) {
      setState(() => _isLoadingAudio = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: Text(widget.artworkName)),
      body: _isLoadingExplanation
          ? const Center(child: CircularProgressIndicator())
          : _explanation == null
              ? const Center(child: Text('Failed to load explanation'))
              : SingleChildScrollView(
                  child: Column(
                    children: [
                      ExplanationCard(
                        explanation: _explanation!,
                        onTtsPlay: _isLoadingAudio ? null : _playAudio,
                      ),
                      const SizedBox(height: 16),
                      if (_isLoadingAudio)
                        const CircularProgressIndicator()
                      else
                        AudioPlayerWidget(audioPlayer: _audioPlayer),
                    ],
                  ),
                ),
    );
  }
}
```

## API Endpoints

### 1. Generate Explanation

**Endpoint:** `POST /api/v1/content/explanation`

**Request Body:**

```json
{
  "artwork_name": "Mona Lisa",
  "artist": "Leonardo da Vinci",
  "period": "Renaissance",
  "language": "en",
  "description": "Optional additional description"
}
```

**Response:**

```json
{
  "title": "Mona Lisa - A Renaissance Masterpiece",
  "summary": "Brief summary...",
  "historical_context": "Historical background...",
  "artistic_analysis": "Artistic techniques...",
  "cultural_significance": "Cultural impact...",
  "interesting_facts": ["Fact 1", "Fact 2"],
  "language": "en"
}
```

### 2. Generate TTS Audio

**Endpoint:** `POST /api/v1/content/tts/generate`

**Request Body:**

```json
{
  "text": "Text to convert to speech",
  "language": "en",
  "voice": "optional_voice_id",
  "speed": 1.0
}
```

**Response:** Binary audio file (MP3)

## Error Handling

所有UseCases都返回`Either<Failure, T>`类型：

- `Left(ServerFailure)` - 服务器错误
- `Left(NetworkFailure)` - 网络连接错误
- `Left(TimeoutFailure)` - 请求超时
- `Left(ValidationFailure)` - 参数验证错误
- `Right(result)` - 成功结果

## Notes

1. **TTS音频处理**: 当前实现返回base64编码的音频数据URL。在生产环境中，应该将音频保存到临时文件并返回文件路径。

2. **缓存**: 可以考虑添加本地缓存以减少API调用。

3. **语言支持**: 支持多种语言代码（en, zh, ja等），需要确保后端API支持对应的语言。

4. **音频格式**: 后端返回MP3格式，`just_audio`包支持跨平台播放。

5. **依赖注入**: 使用Riverpod进行依赖注入，所有providers都是自动管理的。
