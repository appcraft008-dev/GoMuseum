/// GoMuseum 讲解页 — 暖纸手册定稿（FinalGuide）
///
/// 装裱画框 + 居中衬线标题 + TTS 播放器 + 讲解正文（含「看点」分隔）
/// + AI 问答（建议问题 chips + 输入框 + 麦克风）。
library;

import 'dart:convert';
import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:gomuseum_app/core/services/tts_service.dart';
import 'package:gomuseum_app/features/content/domain/entities/explanation.dart';
import 'package:gomuseum_app/features/content/domain/usecases/generate_explanation.dart';
import 'package:gomuseum_app/features/content/domain/usecases/generate_tts_audio.dart';
import 'package:gomuseum_app/features/content/presentation/providers/content_providers.dart';
import 'package:gomuseum_app/features/recognition/domain/entities/recognition_result.dart';
import 'package:gomuseum_app/features/recognition/presentation/providers/recognition_providers.dart';
import 'package:gomuseum_app/ui/gm/gm.dart';
import 'package:just_audio/just_audio.dart';
import 'package:path_provider/path_provider.dart';

/// 讲解页路由参数
class GuideArgs {
  const GuideArgs({required this.result, this.imagePath, this.imageUrl});

  final RecognitionResult result;

  /// 本地拍摄照片路径（识别流程）
  final String? imagePath;

  /// 网络图片（馆藏目录流程，Wikimedia 缩略图）
  final String? imageUrl;
}

/// 问答记录
class _QaEntry {
  const _QaEntry({required this.question, this.answer});

  final String question;
  final String? answer;
}

class GuidePage extends ConsumerStatefulWidget {
  const GuidePage({super.key, required this.args});

  final GuideArgs args;

  @override
  ConsumerState<GuidePage> createState() => _GuidePageState();
}

class _GuidePageState extends ConsumerState<GuidePage> {
  final TtsService _tts = TtsService();
  final TextEditingController _questionController = TextEditingController();
  final ScrollController _scrollController = ScrollController();

  Explanation? _explanation;
  String? _loadError;
  bool _starred = false;

  /// TTS 音频准备状态
  bool _audioLoading = false;
  bool _audioReady = false;
  static const _speeds = [1.0, 1.25, 1.5, 0.75];
  int _speedIndex = 0;

  final List<_QaEntry> _qa = [];
  bool _asking = false;

  RecognitionResult get _result => widget.args.result;

  /// MVP 中文优先；多语言切换接入设置页后改为读取语言设置
  String get _language => 'zh';

  @override
  void initState() {
    super.initState();
    _loadExplanation();
  }

  @override
  void dispose() {
    _tts.dispose();
    _questionController.dispose();
    _scrollController.dispose();
    super.dispose();
  }

  Future<void> _loadExplanation() async {
    setState(() {
      _explanation = null;
      _loadError = null;
    });
    final useCase = ref.read(generateExplanationUseCaseProvider);
    final result = await useCase(GenerateExplanationParams(
      artworkName: _result.artworkName,
      artist: _result.artist,
      period: _result.period,
      language: _language,
      description: _result.description,
    ));
    if (!mounted) return;
    result.fold(
      (failure) => setState(() => _loadError = failure.message),
      (explanation) => setState(() => _explanation = explanation),
    );
  }

  String get _fullNarration {
    final e = _explanation;
    if (e == null) return '';
    return [
      e.summary,
      e.historicalContext,
      e.artisticAnalysis,
      e.culturalSignificance,
    ].where((s) => s.trim().isNotEmpty).join('\n\n');
  }

  Future<void> _togglePlay() async {
    if (_explanation == null) return;
    if (_tts.isPlaying) {
      await _tts.pause();
      setState(() {});
      return;
    }
    if (_audioReady) {
      await _tts.resume();
      setState(() {});
      return;
    }
    if (_audioLoading) return;

    setState(() => _audioLoading = true);
    final useCase = ref.read(generateTtsAudioUseCaseProvider);
    final result = await useCase(GenerateTtsAudioParams(
      text: _fullNarration,
      language: _language,
    ));
    if (!mounted) return;
    await result.fold(
      (failure) async {
        setState(() => _audioLoading = false);
        if (mounted) {
          ScaffoldMessenger.of(context).showSnackBar(
            SnackBar(content: Text('语音生成失败：${failure.message}')),
          );
        }
      },
      (url) async {
        try {
          final playable = await _materializeAudio(url);
          await _tts.play(playable);
          if (mounted) {
            setState(() {
              _audioLoading = false;
              _audioReady = true;
            });
          }
        } catch (e) {
          if (mounted) {
            setState(() => _audioLoading = false);
            ScaffoldMessenger.of(context).showSnackBar(
              SnackBar(content: Text('音频播放失败：$e')),
            );
          }
        }
      },
    );
  }

  /// data: URI 的 base64 音频落盘为临时文件，其余按 URL 直接播放
  Future<String> _materializeAudio(String url) async {
    if (!url.startsWith('data:audio')) return url;
    final base64Data = url.substring(url.indexOf(',') + 1);
    final bytes = base64Decode(base64Data);
    final dir = await getTemporaryDirectory();
    final file = File(
        '${dir.path}/gomuseum_tts_${DateTime.now().millisecondsSinceEpoch}.mp3');
    await file.writeAsBytes(bytes);
    return 'file://${file.path}';
  }

  Future<void> _cycleSpeed() async {
    setState(() => _speedIndex = (_speedIndex + 1) % _speeds.length);
    await _tts.setSpeed(_speeds[_speedIndex]);
  }

  Future<void> _ask(String question) async {
    final q = question.trim();
    if (q.isEmpty || _asking) return;
    _questionController.clear();
    setState(() {
      _asking = true;
      _qa.add(_QaEntry(question: q));
    });
    _scrollToBottom();

    try {
      final dio = ref.read(dioProvider);
      final response = await dio.post('/api/v1/chat/ask', data: {
        'question': q,
        'context':
            '${_result.artworkName}，${_result.artist}，${_result.period}。${_result.description}',
        'language': _language,
      });
      final answer =
          (response.data as Map<String, dynamic>)['answer'] as String?;
      if (!mounted) return;
      setState(() {
        _qa.last = _QaEntry(question: q, answer: answer ?? '（未返回回答）');
        _asking = false;
      });
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _qa.last = _QaEntry(question: q, answer: '回答失败，请稍后再试。');
        _asking = false;
      });
    }
    _scrollToBottom();
  }

  void _scrollToBottom() {
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (_scrollController.hasClients) {
        _scrollController.animateTo(
          _scrollController.position.maxScrollExtent,
          duration: const Duration(milliseconds: 250),
          curve: Curves.easeOut,
        );
      }
    });
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: GmColors.bg,
      body: SafeArea(
        child: Column(
          children: [
            _topBar(context),
            Expanded(
              child: SingleChildScrollView(
                controller: _scrollController,
                padding: const EdgeInsets.fromLTRB(24, 12, 24, 12),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.stretch,
                  children: [
                    GmFramedImage(
                      image: widget.args.imagePath != null
                          ? FileImage(File(widget.args.imagePath!))
                          : (widget.args.imageUrl != null
                              ? NetworkImage(widget.args.imageUrl!)
                                  as ImageProvider
                              : null),
                      height: 186,
                    ),
                    const SizedBox(height: 12),
                    _titleBlock(),
                    const SizedBox(height: 16),
                    _player(),
                    const SizedBox(height: 10),
                    const GmHairline(),
                    const SizedBox(height: 12),
                    _body(),
                    if (_qa.isNotEmpty) ...[
                      const SizedBox(height: 16),
                      _qaList(),
                    ],
                  ],
                ),
              ),
            ),
            _qaInput(),
          ],
        ),
      ),
    );
  }

  Widget _topBar(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.fromLTRB(18, 12, 18, 0),
      child: Row(
        children: [
          GestureDetector(
            onTap: () => context.canPop() ? context.pop() : context.go('/'),
            behavior: HitTestBehavior.opaque,
            child: const GmIcon(GmIcons.back, size: 20, color: GmColors.ink),
          ),
          Expanded(
            child: Text(
              '语音导览',
              textAlign: TextAlign.center,
              style:
                  GmText.sans(size: 11, letterSpacing: 3, color: GmColors.sub),
            ),
          ),
          GestureDetector(
            onTap: () => setState(() => _starred = !_starred),
            behavior: HitTestBehavior.opaque,
            child: GmIcon(
              GmIcons.star,
              size: 20,
              color: GmColors.accent,
              fill: _starred,
            ),
          ),
        ],
      ),
    );
  }

  Widget _titleBlock() {
    return Column(
      children: [
        Text(
          _result.artworkName,
          textAlign: TextAlign.center,
          style:
              GmText.serif(size: 22, weight: FontWeight.w700, letterSpacing: 1),
        ),
        const SizedBox(height: 8),
        const GmDiamond(width: 120),
        const SizedBox(height: 7),
        Text(
          '${_result.artist} · ${_result.period}',
          textAlign: TextAlign.center,
          style: GmText.sans(size: 12, color: GmColors.sub),
        ),
      ],
    );
  }

  Widget _player() {
    return StreamBuilder<Duration>(
      stream: _tts.positionStream,
      builder: (context, positionSnap) {
        return StreamBuilder<Duration?>(
          stream: _tts.durationStream,
          builder: (context, durationSnap) {
            final position = positionSnap.data ?? Duration.zero;
            final duration = durationSnap.data ?? Duration.zero;
            final progress = duration.inMilliseconds == 0
                ? 0.0
                : (position.inMilliseconds / duration.inMilliseconds)
                    .clamp(0.0, 1.0);
            return Row(
              children: [
                GestureDetector(
                  onTap: _togglePlay,
                  child: Container(
                    width: 48,
                    height: 48,
                    decoration: const BoxDecoration(
                      color: GmColors.ctaBg,
                      shape: BoxShape.circle,
                    ),
                    alignment: Alignment.center,
                    child: _audioLoading
                        ? const SizedBox(
                            width: 18,
                            height: 18,
                            child: CircularProgressIndicator(
                              strokeWidth: 2,
                              color: GmColors.ctaInk,
                            ),
                          )
                        : StreamBuilder<PlayerState>(
                            stream: _tts.playerStateStream,
                            builder: (context, snap) {
                              final playing = snap.data?.playing ?? false;
                              return GmIcon(
                                playing ? GmIcons.pause : GmIcons.play,
                                size: 19,
                                color: GmColors.ctaInk,
                                strokeWidth: 2,
                              );
                            },
                          ),
                  ),
                ),
                const SizedBox(width: 14),
                Expanded(
                  child: Column(
                    children: [
                      Stack(
                        clipBehavior: Clip.none,
                        children: [
                          Container(height: 2, color: GmColors.line),
                          FractionallySizedBox(
                            widthFactor: progress,
                            child: Container(height: 2, color: GmColors.accent),
                          ),
                          Positioned(
                            left: 0,
                            right: 0,
                            top: -3.5,
                            child: Align(
                              alignment: Alignment(progress * 2 - 1, 0),
                              child: Container(
                                width: 9,
                                height: 9,
                                decoration: const BoxDecoration(
                                  color: GmColors.accentDeep,
                                  shape: BoxShape.circle,
                                ),
                              ),
                            ),
                          ),
                        ],
                      ),
                      const SizedBox(height: 7),
                      Row(
                        mainAxisAlignment: MainAxisAlignment.spaceBetween,
                        children: [
                          Text(_format(position),
                              style:
                                  GmText.sans(size: 11, color: GmColors.sub)),
                          Text(_format(duration),
                              style:
                                  GmText.sans(size: 11, color: GmColors.sub)),
                        ],
                      ),
                    ],
                  ),
                ),
                const SizedBox(width: 14),
                GestureDetector(
                  onTap: _cycleSpeed,
                  child: Container(
                    padding:
                        const EdgeInsets.symmetric(horizontal: 10, vertical: 5),
                    decoration: BoxDecoration(
                      color: GmColors.surface,
                      border: Border.all(color: GmColors.line),
                      borderRadius: BorderRadius.circular(999),
                    ),
                    child: Text(
                      '${_speeds[_speedIndex]}×',
                      style: GmText.sans(size: 11.5, color: GmColors.sub),
                    ),
                  ),
                ),
              ],
            );
          },
        );
      },
    );
  }

  String _format(Duration d) {
    final m = d.inMinutes;
    final s = (d.inSeconds % 60).toString().padLeft(2, '0');
    return '$m:$s';
  }

  Widget _body() {
    if (_loadError != null) {
      return Column(
        children: [
          Text('讲解生成失败',
              style: GmText.serif(size: 15, weight: FontWeight.w700)),
          const SizedBox(height: 6),
          Text(_loadError!,
              textAlign: TextAlign.center,
              style: GmText.sans(size: 12, color: GmColors.sub)),
          const SizedBox(height: 12),
          GmTicketButton(label: '重试', onTap: _loadExplanation, height: 38),
        ],
      );
    }
    final e = _explanation;
    if (e == null) {
      return Padding(
        padding: const EdgeInsets.symmetric(vertical: 28),
        child: Column(
          children: [
            const CircularProgressIndicator(),
            const SizedBox(height: 12),
            Text('正在为你撰写讲解…',
                style: GmText.sans(size: 12, color: GmColors.sub)),
          ],
        ),
      );
    }

    final intro = [e.summary, e.historicalContext]
        .where((s) => s.trim().isNotEmpty)
        .join('\n\n');
    final highlight = [e.artisticAnalysis, e.culturalSignificance]
        .where((s) => s.trim().isNotEmpty)
        .join('\n\n');

    final paragraphStyle = GmText.sans(size: 13.5, height: 1.9);
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(intro, style: paragraphStyle, textAlign: TextAlign.justify),
        if (highlight.isNotEmpty) ...[
          const SizedBox(height: 11),
          Row(
            children: [
              Text('看点',
                  style: GmText.serif(
                      size: 14,
                      weight: FontWeight.w700,
                      color: GmColors.accentDeep)),
              const SizedBox(width: 10),
              const Expanded(child: GmHairline()),
            ],
          ),
          const SizedBox(height: 9),
          Text(highlight, style: paragraphStyle, textAlign: TextAlign.justify),
        ],
      ],
    );
  }

  Widget _qaList() {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          children: [
            Text('问答',
                style: GmText.serif(
                    size: 14,
                    weight: FontWeight.w700,
                    color: GmColors.accentDeep)),
            const SizedBox(width: 10),
            const Expanded(child: GmHairline()),
          ],
        ),
        for (final entry in _qa) ...[
          const SizedBox(height: 10),
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 13, vertical: 7),
            decoration: BoxDecoration(
              color: GmColors.chipBg,
              borderRadius: BorderRadius.circular(999),
            ),
            child: Text(entry.question, style: GmText.sans(size: 12)),
          ),
          const SizedBox(height: 8),
          if (entry.answer == null)
            Row(
              children: [
                const SizedBox(
                  width: 12,
                  height: 12,
                  child: CircularProgressIndicator(strokeWidth: 1.6),
                ),
                const SizedBox(width: 8),
                Text('思考中…', style: GmText.sans(size: 12, color: GmColors.sub)),
              ],
            )
          else
            Text(
              entry.answer!,
              style: GmText.sans(size: 13, height: 1.8),
              textAlign: TextAlign.justify,
            ),
        ],
      ],
    );
  }

  Widget _qaInput() {
    const suggestions = ['这幅画好在哪里？', '画家当时经历了什么？'];
    return Padding(
      padding: const EdgeInsets.fromLTRB(24, 0, 24, 14),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          if (_qa.isEmpty)
            Padding(
              padding: const EdgeInsets.only(bottom: 10),
              child: Row(
                children: [
                  for (final q in suggestions) ...[
                    GestureDetector(
                      onTap: () => _ask(q),
                      child: Container(
                        padding: const EdgeInsets.symmetric(
                            horizontal: 13, vertical: 7),
                        decoration: BoxDecoration(
                          color: GmColors.chipBg,
                          borderRadius: BorderRadius.circular(999),
                        ),
                        child: Text(q, style: GmText.sans(size: 12)),
                      ),
                    ),
                    const SizedBox(width: 8),
                  ],
                ],
              ),
            ),
          Row(
            children: [
              Expanded(
                child: Container(
                  height: 46,
                  padding: const EdgeInsets.symmetric(horizontal: 18),
                  decoration: BoxDecoration(
                    color: GmColors.surface,
                    border: Border.all(color: GmColors.line),
                    borderRadius: BorderRadius.circular(999),
                  ),
                  alignment: Alignment.centerLeft,
                  child: TextField(
                    controller: _questionController,
                    style: GmText.sans(size: 13.5),
                    decoration: InputDecoration(
                      hintText: '问问这幅画……',
                      hintStyle: GmText.sans(size: 13.5, color: GmColors.faint),
                      border: InputBorder.none,
                      isDense: true,
                    ),
                    textInputAction: TextInputAction.send,
                    onSubmitted: _ask,
                  ),
                ),
              ),
              const SizedBox(width: 10),
              GestureDetector(
                onTap: () {
                  if (_questionController.text.trim().isNotEmpty) {
                    _ask(_questionController.text);
                  } else {
                    ScaffoldMessenger.of(context).showSnackBar(
                      const SnackBar(content: Text('语音问答即将开放，先打字问问吧')),
                    );
                  }
                },
                child: Container(
                  width: 46,
                  height: 46,
                  decoration: const BoxDecoration(
                    color: GmColors.ctaBg,
                    shape: BoxShape.circle,
                  ),
                  alignment: Alignment.center,
                  child: const GmIcon(GmIcons.mic,
                      size: 20, color: GmColors.ctaInk),
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }
}
