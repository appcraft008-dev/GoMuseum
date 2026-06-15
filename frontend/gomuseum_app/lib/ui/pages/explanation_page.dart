import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:easy_localization/easy_localization.dart';
import 'package:just_audio/just_audio.dart';
import '../../core/services/tts_service.dart';
import '../../core/services/voice_qa_service.dart';
import '../../features/recognition/presentation/providers/recognition_providers.dart';
import '../../theme/tokens.dart';

/// 艺术品讲解页面（集成TTS和语音问答）
class ExplanationPage extends ConsumerStatefulWidget {
  final String artworkId;
  final String artworkName;
  final String description;

  const ExplanationPage({
    super.key,
    required this.artworkId,
    required this.artworkName,
    required this.description,
  });

  @override
  ConsumerState<ExplanationPage> createState() => _ExplanationPageState();
}

class _ExplanationPageState extends ConsumerState<ExplanationPage> {
  late final TtsService _ttsService;
  late final VoiceQaService _voiceQaService;

  bool _isPlaying = false;
  bool _isListening = false;
  bool _isProcessing = false;
  String? _currentAnswer;
  Duration _position = Duration.zero;
  Duration _duration = Duration.zero;

  @override
  void initState() {
    super.initState();
    _ttsService = TtsService();
    _voiceQaService = VoiceQaService(dio: ref.read(dioProvider));

    // 监听播放状态
    _ttsService.playerStateStream.listen((state) {
      if (mounted) {
        setState(() {
          _isPlaying = state.playing;
        });
      }
    });

    // 监听播放位置
    _ttsService.positionStream.listen((position) {
      if (mounted) {
        setState(() {
          _position = position;
        });
      }
    });

    // 监听时长
    _ttsService.durationStream.listen((duration) {
      if (mounted && duration != null) {
        setState(() {
          _duration = duration;
        });
      }
    });
  }

  @override
  void dispose() {
    _ttsService.dispose();
    _voiceQaService.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: Text(widget.artworkName),
      ),
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            _buildArtworkInfo(),
            const SizedBox(height: 24),
            _buildTtsController(),
            const SizedBox(height: 24),
            _buildVoiceQaSection(),
            const SizedBox(height: 24),
            _buildDescription(),
          ],
        ),
      ),
    );
  }

  Widget _buildArtworkInfo() {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              widget.artworkName,
              style: const TextStyle(fontSize: 20, fontWeight: FontWeight.bold),
            ),
            const SizedBox(height: 8),
            Text(
              '点击下方播放按钮收听AI讲解',
              style: TextStyle(color: Colors.grey[600], fontSize: 14),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildTtsController() {
    return Card(
      color: const Color(GMColors.surfacePrimary),
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          children: [
            IconButton(
              onPressed: _handlePlayPause,
              iconSize: 64,
              icon: Icon(
                _isPlaying
                    ? Icons.pause_circle_filled
                    : Icons.play_circle_filled,
                color: const Color(GMColors.brandPrimary),
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildVoiceQaSection() {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            const Text('Voice Q&A',
                style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold)),
            const SizedBox(height: 16),
            ElevatedButton.icon(
              onPressed:
                  _isListening || _isProcessing ? null : _handleVoiceQuestion,
              icon: Icon(_isListening ? Icons.mic : Icons.mic_none),
              label: Text(_isListening ? 'Listening...' : 'Ask Question'),
              style: ElevatedButton.styleFrom(
                backgroundColor: const Color(GMColors.brandPrimary),
                padding: const EdgeInsets.symmetric(vertical: 16),
              ),
            ),
            if (_currentAnswer != null) ...[
              const SizedBox(height: 16),
              Container(
                padding: const EdgeInsets.all(12),
                decoration: BoxDecoration(
                  color: Colors.blue[50],
                  borderRadius: BorderRadius.circular(8),
                ),
                child: Text(_currentAnswer!),
              ),
            ],
          ],
        ),
      ),
    );
  }

  Widget _buildDescription() {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Text(widget.description,
            style: const TextStyle(fontSize: 14, height: 1.6)),
      ),
    );
  }

  Future<void> _handlePlayPause() async {
    if (_isPlaying) {
      await _ttsService.pause();
    } else {
      await _ttsService.resume();
    }
  }

  Future<void> _handleVoiceQuestion() async {
    setState(() => _isListening = true);
    await _voiceQaService.voiceAskQuestion(
      artworkId: widget.artworkId,
      context: widget.description,
      onAnswer: (answer) => setState(() {
        _isListening = false;
        _currentAnswer = answer;
      }),
      onError: (error) => setState(() => _isListening = false),
    );
  }
}
