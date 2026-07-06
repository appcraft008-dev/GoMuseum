/// GoMuseum 讲解页 — 暖纸手册定稿
///
/// 双入口：
///   A. slug+qid 入口 → A5 ObjectContent（Hero 折叠 / 墙签 / 信息表 / tabs / 待完善）
///   B. RecognitionResult 入口 → 旧 AI 生成路径（识别流程，保留兼容）
///
/// AI 问答底栏（session B 交互）→ 本文件只留静态挂载点壳。
library;

import 'dart:async';
import 'dart:convert';
import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:gomuseum_app/core/network/image_request.dart';
import 'package:gomuseum_app/core/services/tts_service.dart';
import 'package:gomuseum_app/features/content/data/models/object_content_model.dart';
import 'package:gomuseum_app/features/content/data/models/object_list_model.dart';
import 'package:gomuseum_app/features/content/domain/entities/explanation.dart';
import 'package:gomuseum_app/features/content/domain/usecases/generate_explanation.dart';
import 'package:gomuseum_app/features/content/domain/usecases/generate_tts_audio.dart';
import 'package:gomuseum_app/features/content/presentation/providers/catalog_providers.dart';
import 'package:gomuseum_app/features/content/presentation/providers/content_providers.dart';
import 'package:gomuseum_app/features/guide/presentation/logic/guide_layering.dart';
import 'package:gomuseum_app/features/guide/presentation/widgets/guide_audio_player.dart';
import 'package:gomuseum_app/features/guide/presentation/widgets/guide_question_list.dart';
import 'package:gomuseum_app/features/guide/presentation/widgets/guide_deep_sheet.dart';
import 'package:gomuseum_app/features/guide/presentation/widgets/image_gallery.dart';
import 'package:gomuseum_app/features/content/presentation/providers/object_list_notifier.dart';
import 'package:gomuseum_app/features/recognition/domain/entities/recognition_result.dart';
import 'package:gomuseum_app/features/recognition/presentation/providers/recognition_providers.dart';
import 'package:gomuseum_app/l10n/app_localizations.dart';
import 'package:gomuseum_app/features/settings/presentation/providers/language_provider.dart';
import 'package:gomuseum_app/theme/gm_theme_x.dart';
import 'package:gomuseum_app/ui/gm/gm.dart';
import 'package:just_audio/just_audio.dart';
import 'package:path_provider/path_provider.dart';

// ---------------------------------------------------------------------------
// Route args
// ---------------------------------------------------------------------------

/// 讲解页路由参数。
///
/// 两种入口（互斥）：
///   1. `slug` + `qid` → A5 ObjectContent 路径（馆藏列表点卡）
///   2. `result` → 识别路径（旧 AI 生成流程）
///
/// [result] 设为可选；当 slug+qid 均有值时忽略 result。
class GuideArgs {
  const GuideArgs({
    this.result,
    this.imagePath,
    this.imageUrl,
    this.slug,
    this.qid,
  }) : assert(
          (slug != null && qid != null) || result != null,
          'GuideArgs 需提供 (slug+qid) 或 result 其中一种',
        );

  /// 识别结果（识别路径；slug+qid 路径可为 null）
  final RecognitionResult? result;

  /// 本地拍摄照片路径（识别流程）
  final String? imagePath;

  /// 网络图片（馆藏目录流程，Wikimedia 缩略图）
  final String? imageUrl;

  /// 馆 slug（馆藏列表流程）
  final String? slug;

  /// 藏品 qid（馆藏列表流程）
  final String? qid;

  /// 是否走 A5 内容路径
  bool get useA5 => slug != null && qid != null;
}

// ---------------------------------------------------------------------------
// Legacy QA entry (recognition path)
// ---------------------------------------------------------------------------

class _QaEntry {
  const _QaEntry({required this.question, this.answer});

  final String question;
  final String? answer;
}

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------

class GuidePage extends ConsumerStatefulWidget {
  const GuidePage({super.key, required this.args});

  final GuideArgs args;

  @override
  ConsumerState<GuidePage> createState() => _GuidePageState();
}

class _GuidePageState extends ConsumerState<GuidePage>
    with TickerProviderStateMixin {
  // ── shared
  bool _starred = false;

  // ── A5 path: facts accordion
  bool _factsExpanded = false;

  // 朗读倍速档位（legacy 识别路径用）
  static const _speeds = [1.0, 1.25, 1.5, 0.75];

  // ── A5 path: generating poll（懒生成体验：约 1-3 分钟出内容）
  Timer? _pollTimer;
  int _pollCount = 0;

  /// 本次访问是否轮询过（=内容曾在生成中）。用于返回时刷新列表角标。
  bool _didPoll = false;

  /// 安全兜底硬顶：20s×45 = 15 分钟。正常以后端 `generating` 为准提前停；
  /// 此上限仅防信号异常时无限轮询。
  static const int _maxPolls = 45;

  // ── legacy recognition path
  final TtsService _legacyTts = TtsService();
  final TextEditingController _questionController = TextEditingController();
  final ScrollController _scrollController = ScrollController();
  Explanation? _explanation;
  String? _loadError;
  bool _legacyAudioLoading = false;
  bool _legacyAudioReady = false;
  int _legacySpeedIndex = 0;
  final List<_QaEntry> _qa = [];
  bool _asking = false;

  // ── language
  String get _language => apiLanguage(ref.read(languageProvider));

  @override
  void initState() {
    super.initState();
    if (!widget.args.useA5) {
      _loadExplanation();
    }
  }

  @override
  void dispose() {
    _pollTimer?.cancel();
    _legacyTts.dispose();
    _questionController.dispose();
    _scrollController.dispose();
    super.dispose();
  }

  // ── A5: poll while status != ready（幂等：重复调用不重置计时器/计数）
  void _startPolling({required String slug, required String qid}) {
    if (_pollTimer != null) return;
    _didPoll = true;
    _pollCount = 0;
    _pollTimer = Timer.periodic(const Duration(seconds: 20), (_) {
      _pollCount++;
      if (_pollCount > _maxPolls) {
        _stopPolling();
        return;
      }
      ref.invalidate(objectContentProvider((slug: slug, qid: qid)));
    });
  }

  void _stopPolling() {
    _pollTimer?.cancel();
    _pollTimer = null;
  }

  // ── Legacy path methods ──────────────────────────────────────────────────

  RecognitionResult get _result => widget.args.result!;

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
      e.culturalSignificance
    ].where((s) => s.trim().isNotEmpty).join('\n\n');
  }

  Future<void> _toggleLegacyPlay() async {
    if (_explanation == null) return;
    if (_legacyTts.isPlaying) {
      await _legacyTts.pause();
      setState(() {});
      return;
    }
    if (_legacyAudioReady) {
      await _legacyTts.resume();
      setState(() {});
      return;
    }
    if (_legacyAudioLoading) return;

    setState(() => _legacyAudioLoading = true);
    final useCase = ref.read(generateTtsAudioUseCaseProvider);
    final result = await useCase(GenerateTtsAudioParams(
      text: _fullNarration,
      language: _language,
    ));
    if (!mounted) return;
    await result.fold(
      (failure) async {
        setState(() => _legacyAudioLoading = false);
        if (mounted) {
          ScaffoldMessenger.of(context).showSnackBar(
            SnackBar(content: Text('语音生成失败：${failure.message}')),
          );
        }
      },
      (url) async {
        try {
          final playable = await _materializeAudio(url);
          await _legacyTts.play(playable);
          if (mounted) {
            setState(() {
              _legacyAudioLoading = false;
              _legacyAudioReady = true;
            });
          }
        } catch (e) {
          if (mounted) setState(() => _legacyAudioLoading = false);
        }
      },
    );
  }

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

  Future<void> _cycleLegacySpeed() async {
    setState(
        () => _legacySpeedIndex = (_legacySpeedIndex + 1) % _speeds.length);
    await _legacyTts.setSpeed(_speeds[_legacySpeedIndex]);
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
      final l10n = AppLocalizations.of(context)!;
      setState(() {
        _qa.last = _QaEntry(question: q, answer: answer ?? l10n.guideNoAnswer);
        _asking = false;
      });
    } catch (e) {
      if (!mounted) return;
      final l10n = AppLocalizations.of(context)!;
      setState(() {
        _qa.last = _QaEntry(question: q, answer: l10n.guideAnswerFailed);
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

  // ── Build ─────────────────────────────────────────────────────────────────

  @override
  Widget build(BuildContext context) {
    if (widget.args.useA5) {
      return _buildA5Page(context);
    }
    return _buildLegacyPage(context);
  }

  // =========================================================================
  // A5 Content Path
  // =========================================================================

  Widget _buildA5Page(BuildContext context) {
    final gm = context.gm;
    final slug = widget.args.slug!;
    final qid = widget.args.qid!;
    final contentAsync =
        ref.watch(objectContentProvider((slug: slug, qid: qid)));

    return contentAsync.when(
      loading: () => _A5LoadingScaffold(gm: gm, onBack: () => _goBack(context)),
      error: (err, _) => _A5ErrorScaffold(
        gm: gm,
        onBack: () => _goBack(context),
        onRetry: () =>
            ref.invalidate(objectContentProvider((slug: slug, qid: qid))),
      ),
      data: (content) {
        // ① 部分就绪流式：先看主讲解是否已落库。
        // 主讲解有 → 立即渲染（不管 generating）；generating 时深度区显「生成中」并继续轮询，
        // 深度模块/问答随后填入。用户不用等全部生成完。
        final hasHero = GuideLayering.from(content).hasHero;
        if (hasHero) {
          if (content.generating) {
            _startPolling(slug: slug, qid: qid);
          } else {
            _stopPolling();
          }
          return Scaffold(
            backgroundColor: gm.bg,
            body: NestedScrollView(
              headerSliverBuilder: (context, _) => [
                _A5HeroSliverAppBar(
                  content: content,
                  starred: _starred,
                  onBack: () => _goBack(context),
                  onToggleStar: () => setState(() => _starred = !_starred),
                ),
              ],
              body: _A5Body(
                content: content,
                slug: slug,
                language: _language,
                deepGenerating: content.generating,
                factsExpanded: _factsExpanded,
                onToggleFacts: () =>
                    setState(() => _factsExpanded = !_factsExpanded),
              ),
            ),
            bottomNavigationBar: const _AskBar(),
          );
        }

        // 主讲解还没有：沿用三态。
        // 2) 生成中 → 「生成中」+ 轮询。
        if (content.generating) {
          _startPolling(slug: slug, qid: qid);
          return _A5GeneratingScaffold(gm: gm, onBack: () => _goBack(context));
        }
        _stopPolling();
        // 3) 非生成中且无内容：资料不足(empty) / 暂未生成可重试(stub)。
        if (content.status == ContentStatus.empty) {
          return _A5UnavailableScaffold(gm: gm, onBack: () => _goBack(context));
        }
        return _A5RetryScaffold(
          gm: gm,
          onBack: () => _goBack(context),
          onRetry: () =>
              ref.invalidate(objectContentProvider((slug: slug, qid: qid))),
        );
      },
    );
  }

  void _goBack(BuildContext context) {
    // 内容曾在生成中（本次可能已变 ready）→ 失效列表，刷新角标。
    // 只在轮询过时失效，避免普通浏览 ready 件返回时列表重载丢滚动位置。
    if (_didPoll) ref.invalidate(objectListProvider);
    context.canPop() ? context.pop() : context.go('/');
  }

  // =========================================================================
  // Legacy Recognition Path
  // =========================================================================

  Widget _buildLegacyPage(BuildContext context) {
    final gm = context.gm;
    return Scaffold(
      backgroundColor: gm.bg,
      body: SafeArea(
        child: Column(
          children: [
            _legacyTopBar(context),
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
                    _legacyTitleBlock(),
                    const SizedBox(height: 16),
                    _legacyPlayer(),
                    const SizedBox(height: 10),
                    const GmHairline(),
                    const SizedBox(height: 12),
                    _legacyBody(),
                    if (_qa.isNotEmpty) ...[
                      const SizedBox(height: 16),
                      _legacyQaList(),
                    ],
                  ],
                ),
              ),
            ),
            _legacyQaInput(),
          ],
        ),
      ),
    );
  }

  Widget _legacyTopBar(BuildContext context) {
    final gm = context.gm;
    return Padding(
      padding: const EdgeInsets.fromLTRB(18, 12, 18, 0),
      child: Row(
        children: [
          GestureDetector(
            onTap: () => _goBack(context),
            behavior: HitTestBehavior.opaque,
            child: GmIcon(GmIcons.back, size: 20, color: gm.ink),
          ),
          Expanded(
            child: Text(AppLocalizations.of(context)!.guideVoiceGuide,
                textAlign: TextAlign.center,
                style: GmText.sans(size: 11, letterSpacing: 3, color: gm.sub)),
          ),
          GestureDetector(
            onTap: () => setState(() => _starred = !_starred),
            behavior: HitTestBehavior.opaque,
            child: GmIcon(GmIcons.star,
                size: 20, color: gm.accent, fill: _starred),
          ),
        ],
      ),
    );
  }

  Widget _legacyTitleBlock() {
    final gm = context.gm;
    return Column(
      children: [
        Text(_result.artworkName,
            textAlign: TextAlign.center,
            style: GmText.serif(
                size: 22, weight: FontWeight.w700, letterSpacing: 1)),
        const SizedBox(height: 8),
        const GmDiamond(width: 120),
        const SizedBox(height: 7),
        Text('${_result.artist} · ${_result.period}',
            textAlign: TextAlign.center,
            style: GmText.sans(size: 12, color: gm.sub)),
      ],
    );
  }

  Widget _legacyPlayer() {
    final gm = context.gm;
    return StreamBuilder<Duration>(
      stream: _legacyTts.positionStream,
      builder: (context, positionSnap) {
        return StreamBuilder<Duration?>(
          stream: _legacyTts.durationStream,
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
                  onTap: _toggleLegacyPlay,
                  child: Container(
                    width: 48,
                    height: 48,
                    decoration:
                        BoxDecoration(color: gm.ctaBg, shape: BoxShape.circle),
                    alignment: Alignment.center,
                    child: _legacyAudioLoading
                        ? SizedBox(
                            width: 18,
                            height: 18,
                            child: CircularProgressIndicator(
                                strokeWidth: 2, color: gm.ctaInk))
                        : StreamBuilder<PlayerState>(
                            stream: _legacyTts.playerStateStream,
                            builder: (context, snap) {
                              final playing = snap.data?.playing ?? false;
                              return GmIcon(
                                  playing ? GmIcons.pause : GmIcons.play,
                                  size: 19,
                                  color: gm.ctaInk,
                                  strokeWidth: 2);
                            }),
                  ),
                ),
                const SizedBox(width: 14),
                Expanded(
                  child: Column(
                    children: [
                      Stack(clipBehavior: Clip.none, children: [
                        Container(height: 2, color: gm.line),
                        FractionallySizedBox(
                            widthFactor: progress,
                            child: Container(height: 2, color: gm.accent)),
                        Positioned(
                          left: 0,
                          right: 0,
                          top: -3.5,
                          child: Align(
                            alignment: Alignment(progress * 2 - 1, 0),
                            child: Container(
                                width: 9,
                                height: 9,
                                decoration: BoxDecoration(
                                    color: gm.accentDeep,
                                    shape: BoxShape.circle)),
                          ),
                        ),
                      ]),
                      const SizedBox(height: 7),
                      Row(
                        mainAxisAlignment: MainAxisAlignment.spaceBetween,
                        children: [
                          Text(_formatDuration(position),
                              style: GmText.sans(size: 11, color: gm.sub)),
                          Text(_formatDuration(duration),
                              style: GmText.sans(size: 11, color: gm.sub)),
                        ],
                      ),
                    ],
                  ),
                ),
                const SizedBox(width: 14),
                GestureDetector(
                  onTap: _cycleLegacySpeed,
                  child: Container(
                    padding:
                        const EdgeInsets.symmetric(horizontal: 10, vertical: 5),
                    decoration: BoxDecoration(
                        color: gm.surface,
                        border: Border.all(color: gm.line),
                        borderRadius: BorderRadius.circular(999)),
                    child: Text('${_speeds[_legacySpeedIndex]}×',
                        style: GmText.sans(size: 11.5, color: gm.sub)),
                  ),
                ),
              ],
            );
          },
        );
      },
    );
  }

  Widget _legacyBody() {
    final gm = context.gm;
    final l10n = AppLocalizations.of(context)!;
    if (_loadError != null) {
      return Column(children: [
        Text(l10n.guideGenFailed,
            style: GmText.serif(size: 15, weight: FontWeight.w700)),
        const SizedBox(height: 6),
        Text(_loadError!,
            textAlign: TextAlign.center,
            style: GmText.sans(size: 12, color: gm.sub)),
        const SizedBox(height: 12),
        GmTicketButton(label: l10n.retry, onTap: _loadExplanation, height: 38),
      ]);
    }
    final e = _explanation;
    if (e == null) {
      return Padding(
        padding: const EdgeInsets.symmetric(vertical: 28),
        child: Column(children: [
          const CircularProgressIndicator(),
          const SizedBox(height: 12),
          Text(l10n.guideWriting, style: GmText.sans(size: 12, color: gm.sub)),
        ]),
      );
    }
    final intro = [e.summary, e.historicalContext]
        .where((s) => s.trim().isNotEmpty)
        .join('\n\n');
    final highlight = [e.artisticAnalysis, e.culturalSignificance]
        .where((s) => s.trim().isNotEmpty)
        .join('\n\n');
    final paragraphStyle =
        GmText.sans(size: 13.5, height: context.gmBodyHeight);
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(intro, style: paragraphStyle, textAlign: TextAlign.justify),
        if (highlight.isNotEmpty) ...[
          const SizedBox(height: 11),
          Row(children: [
            Text(l10n.guideHighlight,
                style: GmText.serif(
                    size: 14, weight: FontWeight.w700, color: gm.accentDeep)),
            const SizedBox(width: 10),
            const Expanded(child: GmHairline()),
          ]),
          const SizedBox(height: 9),
          Text(highlight, style: paragraphStyle, textAlign: TextAlign.justify),
        ],
      ],
    );
  }

  Widget _legacyQaList() {
    final gm = context.gm;
    final l10n = AppLocalizations.of(context)!;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(children: [
          Text(l10n.guideQa,
              style: GmText.serif(
                  size: 14, weight: FontWeight.w700, color: gm.accentDeep)),
          const SizedBox(width: 10),
          const Expanded(child: GmHairline()),
        ]),
        for (final entry in _qa) ...[
          const SizedBox(height: 10),
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 13, vertical: 7),
            decoration: BoxDecoration(
                color: gm.chipBg, borderRadius: BorderRadius.circular(999)),
            child: Text(entry.question, style: GmText.sans(size: 12)),
          ),
          const SizedBox(height: 8),
          if (entry.answer == null)
            Row(children: [
              const SizedBox(
                  width: 12,
                  height: 12,
                  child: CircularProgressIndicator(strokeWidth: 1.6)),
              const SizedBox(width: 8),
              Text(l10n.guideThinking,
                  style: GmText.sans(size: 12, color: gm.sub)),
            ])
          else
            Text(entry.answer!,
                style: GmText.sans(size: 13, height: 1.8),
                textAlign: TextAlign.justify),
        ],
      ],
    );
  }

  Widget _legacyQaInput() {
    final gm = context.gm;
    final l10n = AppLocalizations.of(context)!;
    final suggestions = [l10n.guideQ1, l10n.guideQ2];
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
                            color: gm.chipBg,
                            borderRadius: BorderRadius.circular(999)),
                        child: Text(q, style: GmText.sans(size: 12)),
                      ),
                    ),
                    const SizedBox(width: 8),
                  ],
                ],
              ),
            ),
          Row(children: [
            Expanded(
              child: Container(
                height: 46,
                padding: const EdgeInsets.symmetric(horizontal: 18),
                decoration: BoxDecoration(
                    color: gm.surface,
                    border: Border.all(color: gm.line),
                    borderRadius: BorderRadius.circular(999)),
                alignment: Alignment.centerLeft,
                child: TextField(
                  controller: _questionController,
                  style: GmText.sans(size: 13.5),
                  decoration: InputDecoration(
                    hintText: l10n.guideAskHint,
                    hintStyle: GmText.sans(size: 13.5, color: gm.faint),
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
                    SnackBar(content: Text(l10n.guideVoiceComingSoon)),
                  );
                }
              },
              child: Container(
                width: 46,
                height: 46,
                decoration:
                    BoxDecoration(color: gm.ctaBg, shape: BoxShape.circle),
                alignment: Alignment.center,
                child: GmIcon(GmIcons.mic, size: 20, color: gm.ctaInk),
              ),
            ),
          ]),
        ],
      ),
    );
  }
}

// =============================================================================
// A5 path — extracted widgets (keep guide_page.dart self-contained)
// =============================================================================

String _formatDuration(Duration d) {
  final m = d.inMinutes;
  final s = (d.inSeconds % 60).toString().padLeft(2, '0');
  return '$m:$s';
}

// ---------------------------------------------------------------------------
// State scaffolds
// ---------------------------------------------------------------------------

class _A5LoadingScaffold extends StatelessWidget {
  const _A5LoadingScaffold({required this.gm, required this.onBack});
  final dynamic gm;
  final VoidCallback onBack;

  @override
  Widget build(BuildContext context) {
    final palette = context.gm;
    return Scaffold(
      backgroundColor: palette.bg,
      body: SafeArea(
        child: Column(children: [
          _SimpleTopBar(onBack: onBack),
          Expanded(
              child: Center(
            child: CircularProgressIndicator(
                color: palette.accent, strokeWidth: 2),
          )),
        ]),
      ),
    );
  }
}

class _A5GeneratingScaffold extends StatelessWidget {
  const _A5GeneratingScaffold({required this.gm, required this.onBack});
  final dynamic gm;
  final VoidCallback onBack;

  @override
  Widget build(BuildContext context) {
    final palette = context.gm;
    return Scaffold(
      backgroundColor: palette.bg,
      body: SafeArea(
        child: Column(children: [
          _SimpleTopBar(onBack: onBack),
          Expanded(
              child: Center(
            child: Column(mainAxisSize: MainAxisSize.min, children: [
              CircularProgressIndicator(color: palette.accent, strokeWidth: 2),
              const SizedBox(height: 16),
              Text(AppLocalizations.of(context)!.guideGenerating,
                  style: GmText.sans(size: 13, color: palette.sub)),
            ]),
          )),
        ]),
      ),
    );
  }
}

class _A5ErrorScaffold extends StatelessWidget {
  const _A5ErrorScaffold(
      {required this.gm, required this.onBack, required this.onRetry});
  final dynamic gm;
  final VoidCallback onBack;
  final VoidCallback onRetry;

  @override
  Widget build(BuildContext context) {
    final palette = context.gm;
    return Scaffold(
      backgroundColor: palette.bg,
      body: SafeArea(
        child: Column(children: [
          _SimpleTopBar(onBack: onBack),
          Expanded(
              child: Center(
            child: Column(mainAxisSize: MainAxisSize.min, children: [
              Text(AppLocalizations.of(context)!.loadFailed,
                  style: GmText.serif(size: 15, weight: FontWeight.w700)),
              const SizedBox(height: 12),
              GmTicketButton(
                  label: AppLocalizations.of(context)!.retry,
                  onTap: onRetry,
                  height: 38),
            ]),
          )),
        ]),
      ),
    );
  }
}

/// 资料不足（generating=false 且 status=empty）：诚实告知，不转圈、无重试。
class _A5UnavailableScaffold extends StatelessWidget {
  const _A5UnavailableScaffold({required this.gm, required this.onBack});
  final dynamic gm;
  final VoidCallback onBack;

  @override
  Widget build(BuildContext context) {
    final palette = context.gm;
    return Scaffold(
      backgroundColor: palette.bg,
      body: SafeArea(
        child: Column(children: [
          _SimpleTopBar(onBack: onBack),
          Expanded(
              child: Center(
            child: Padding(
              padding: const EdgeInsets.symmetric(horizontal: 32),
              child: Text(
                AppLocalizations.of(context)!.guideUnavailable,
                textAlign: TextAlign.center,
                style: GmText.sans(size: 14, color: palette.sub),
              ),
            ),
          )),
        ]),
      ),
    );
  }
}

/// 暂未生成（generating=false 且 status=stub）：重试 = 重新拉 content 再触发懒生成。
class _A5RetryScaffold extends StatelessWidget {
  const _A5RetryScaffold(
      {required this.gm, required this.onBack, required this.onRetry});
  final dynamic gm;
  final VoidCallback onBack;
  final VoidCallback onRetry;

  @override
  Widget build(BuildContext context) {
    final palette = context.gm;
    return Scaffold(
      backgroundColor: palette.bg,
      body: SafeArea(
        child: Column(children: [
          _SimpleTopBar(onBack: onBack),
          Expanded(
              child: Center(
            child: Column(mainAxisSize: MainAxisSize.min, children: [
              Text(AppLocalizations.of(context)!.guideNotGenerated,
                  style: GmText.serif(size: 15, weight: FontWeight.w700)),
              const SizedBox(height: 12),
              GmTicketButton(
                  label: AppLocalizations.of(context)!.retry,
                  onTap: onRetry,
                  height: 38),
            ]),
          )),
        ]),
      ),
    );
  }
}

class _SimpleTopBar extends StatelessWidget {
  const _SimpleTopBar({required this.onBack});
  final VoidCallback onBack;

  @override
  Widget build(BuildContext context) {
    final gm = context.gm;
    return Padding(
      padding: const EdgeInsets.fromLTRB(18, 12, 18, 0),
      child: Row(children: [
        GestureDetector(
          onTap: onBack,
          behavior: HitTestBehavior.opaque,
          child: GmIcon(GmIcons.back, size: 20, color: gm.ink),
        ),
        const Spacer(),
      ]),
    );
  }
}

// ---------------------------------------------------------------------------
// Hero collapsing SliverAppBar
// ---------------------------------------------------------------------------

class _A5HeroSliverAppBar extends StatelessWidget {
  const _A5HeroSliverAppBar({
    required this.content,
    required this.starred,
    required this.onBack,
    required this.onToggleStar,
  });

  final ObjectContent content;
  final bool starred;
  final VoidCallback onBack;
  final VoidCallback onToggleStar;

  @override
  Widget build(BuildContext context) {
    final gm = context.gm;
    final hasImage = content.images.isNotEmpty;

    return SliverAppBar(
      expandedHeight: 286,
      pinned: true,
      backgroundColor: gm.bg,
      leading: GestureDetector(
        onTap: onBack,
        behavior: HitTestBehavior.opaque,
        child: Center(child: GmIcon(GmIcons.back, size: 20, color: gm.ink)),
      ),
      title: Text(
        content.title,
        style: GmText.serif(size: 14.5, weight: FontWeight.w700),
        overflow: TextOverflow.ellipsis,
      ),
      centerTitle: true,
      actions: [
        GestureDetector(
          onTap: onToggleStar,
          behavior: HitTestBehavior.opaque,
          child: Padding(
            padding: const EdgeInsets.only(right: 16),
            child:
                GmIcon(GmIcons.star, size: 20, color: gm.accent, fill: starred),
          ),
        ),
      ],
      flexibleSpace: FlexibleSpaceBar(
        collapseMode: CollapseMode.parallax,
        background: hasImage
            ? _HeroImages(images: content.images, title: content.title)
            : _HeroPlaceholder(title: content.title),
      ),
    );
  }
}

/// 头图区：多图轮播（`images.length > 1`）+ 点击进全屏画廊。单图行为不变。
class _HeroImages extends StatefulWidget {
  const _HeroImages({required this.images, required this.title});

  final List<ObjectImage> images;
  final String title;

  @override
  State<_HeroImages> createState() => _HeroImagesState();
}

class _HeroImagesState extends State<_HeroImages> {
  final PageController _pc = PageController();
  int _i = 0;

  @override
  void dispose() {
    _pc.dispose();
    super.dispose();
  }

  Widget _networkImage(BuildContext context, String url) => Image.network(
        // 关键：Wikimedia 兜底取缩略图而非数十 MB 原图；R2 直链原样透传。
        sizedImageUrl(url, 1080),
        fit: BoxFit.cover,
        headers: kImageRequestHeaders,
        loadingBuilder: (_, child, progress) =>
            progress == null ? child : ColoredBox(color: context.gm.chipBg),
        errorBuilder: (_, __, ___) => ColoredBox(
            color: context.gm.chipBg,
            child: Center(
                child:
                    GmIcon(GmIcons.photo, size: 40, color: context.gm.faint))),
      );

  @override
  Widget build(BuildContext context) {
    final images = widget.images;
    final multi = images.length > 1;
    final credit = images[_i].credit;

    return GestureDetector(
      onTap: () => showImageGallery(context, images: images, initialIndex: _i),
      behavior: HitTestBehavior.opaque,
      child: Stack(
        fit: StackFit.expand,
        children: [
          if (multi)
            PageView.builder(
              controller: _pc,
              itemCount: images.length,
              onPageChanged: (i) => setState(() => _i = i),
              itemBuilder: (_, i) => _networkImage(context, images[i].url),
            )
          else
            _networkImage(context, images.first.url),

          // Bottom gradient scrim
          const Positioned(
            bottom: 0,
            left: 0,
            right: 0,
            height: 160,
            child: DecoratedBox(
              decoration: BoxDecoration(
                gradient: LinearGradient(
                  begin: Alignment.topCenter,
                  end: Alignment.bottomCenter,
                  colors: GmFixed.heroScrim,
                  stops: GmFixed.heroScrimStops,
                ),
              ),
            ),
          ),

          // Title overlay
          Positioned(
            bottom: 42,
            left: 20,
            right: credit != null ? 80 : 20,
            child: Text(
              widget.title,
              style: GmText.serif(
                  size: 22, weight: FontWeight.w700, color: GmFixed.heroTitle),
              maxLines: 2,
              overflow: TextOverflow.ellipsis,
            ),
          ),

          // 页码 i/n（多图时）
          if (multi)
            Positioned(
              bottom: 14,
              left: 0,
              right: 0,
              child: Center(
                child: Container(
                  padding:
                      const EdgeInsets.symmetric(horizontal: 10, vertical: 3),
                  decoration: BoxDecoration(
                      color: Colors.black.withValues(alpha: 0.35),
                      borderRadius: BorderRadius.circular(999)),
                  child: Text('${_i + 1}/${images.length}',
                      style: GmText.sans(
                          size: 10.5, color: Colors.white, letterSpacing: 1)),
                ),
              ),
            ),

          // Credit bottom-right
          if (credit != null && credit.trim().isNotEmpty)
            Positioned(
              bottom: 10,
              right: 12,
              child: Text(
                credit,
                style: GmText.sans(size: 9, color: GmFixed.heroCredit),
              ),
            ),
        ],
      ),
    );
  }
}

class _HeroPlaceholder extends StatelessWidget {
  const _HeroPlaceholder({required this.title});
  final String title;

  @override
  Widget build(BuildContext context) {
    final gm = context.gm;
    return ColoredBox(
      color: gm.surface,
      child: Stack(fit: StackFit.expand, children: [
        Center(child: GmIcon(GmIcons.photo, size: 48, color: gm.faint)),
        Positioned(
          bottom: 42,
          left: 20,
          right: 20,
          child: Text(title,
              style: GmText.serif(
                  size: 22, weight: FontWeight.w700, color: gm.ink),
              maxLines: 2),
        ),
      ]),
    );
  }
}

// ---------------------------------------------------------------------------
// Main scrollable body (wall label + facts + tabs + AI shell)
// ---------------------------------------------------------------------------

/// 分层导览主体：标准导览主角 + 就地展开问题 + 深度内容门票。
/// 作为 NestedScrollView 的 body（滚动内容）；底部追问栏由 Scaffold 固定。
class _A5Body extends StatelessWidget {
  const _A5Body({
    required this.content,
    required this.slug,
    required this.language,
    required this.deepGenerating,
    required this.factsExpanded,
    required this.onToggleFacts,
  });

  final ObjectContent content;
  final String slug;

  /// API 语言参数（繁体已 zh-hant）。
  final String language;

  /// 主讲解已出但后端仍在生成深度/问答 → 深度区显「生成中」提示。
  final bool deepGenerating;
  final bool factsExpanded;
  final VoidCallback onToggleFacts;

  @override
  Widget build(BuildContext context) {
    final gm = context.gm;
    final l10n = AppLocalizations.of(context)!;
    final layer = GuideLayering.from(content);

    return SingleChildScrollView(
      padding: const EdgeInsets.fromLTRB(20, 14, 20, 24),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          _WallLabel(facts: content.facts),
          const SizedBox(height: 8),
          Container(height: 1, color: gm.line),
          _FactsAccordion(
            facts: content.facts,
            expanded: factsExpanded,
            onToggle: onToggleFacts,
          ),
          Container(height: 1, color: gm.line),

          // ◆ 标准导览（主角）
          Padding(
            padding: const EdgeInsets.only(top: 18),
            child: Row(children: [
              Text('◆  ${l10n.guideStandardTour}',
                  style: GmText.serif(
                      size: 12.5,
                      weight: FontWeight.w700,
                      color: gm.accentDeep,
                      letterSpacing: 2)),
              const SizedBox(width: 10),
              Expanded(child: Container(height: 1, color: gm.line)),
            ]),
          ),
          GuideAudioPlayer(
            slug: slug,
            qid: content.qid,
            language: language,
            initialUrl: layer.heroAudioUrl,
          ),
          const SizedBox(height: 14),
          if (layer.hasHero)
            Text(layer.heroBody,
                style: GmText.sans(size: 13.5, height: context.gmBodyHeight),
                textAlign: TextAlign.justify)
          else
            Padding(
              padding: const EdgeInsets.symmetric(vertical: 20),
              child: Text(l10n.toBeRefined,
                  textAlign: TextAlign.center,
                  style: GmText.sans(size: 13, color: gm.faint)),
            ),

          // ── 想深入？点一下 ──
          if (content.suggestedQuestions.isNotEmpty) ...[
            Padding(
              padding: const EdgeInsets.only(top: 20),
              child: Row(children: [
                Expanded(child: Container(height: 1, color: gm.line)),
                Padding(
                  padding: const EdgeInsets.symmetric(horizontal: 9),
                  child: Text(l10n.guideDiveIn,
                      style: GmText.sans(
                          size: 10.5, color: gm.faint, letterSpacing: 1.2)),
                ),
                Expanded(child: Container(height: 1, color: gm.line)),
              ]),
            ),
            const SizedBox(height: 4),
            GuideQuestionList(questions: content.suggestedQuestions),
          ],

          // ① 深度/问答仍在生成 → 轻提示（主讲解已可读）。
          if (deepGenerating)
            Padding(
              padding: const EdgeInsets.only(top: 18),
              child: Row(children: [
                SizedBox(
                  width: 13,
                  height: 13,
                  child: CircularProgressIndicator(
                      strokeWidth: 1.6, color: gm.faint),
                ),
                const SizedBox(width: 10),
                Text(l10n.deepGenerating,
                    style: GmText.sans(size: 12, color: gm.sub)),
              ]),
            ),

          // 📖 深度内容 → 底部抽屉（「作者介绍」为首位 tab，必选常驻）。
          // 入口条件放宽：有深度 tab 或有作者都露出；数字含作者 tab。
          if (layer.hasDeep || content.artist != null)
            Builder(builder: (context) {
              final hasArtist =
                  content.artist != null && content.artist!.name.isNotEmpty;
              final sheetTabCount = layer.deepCount + (hasArtist ? 1 : 0);
              return Padding(
                padding: const EdgeInsets.only(top: 18),
                child: GmTicketButton(
                  label: '${l10n.guideDeepContent}（$sheetTabCount）',
                  icon: GmIcons.doc,
                  trailingIcon: GmIcons.arrowR,
                  onTap: () => showGuideDeepSheet(context, layer.deepTabs,
                      artist: content.artist),
                ),
              );
            }),
        ],
      ),
    );
  }
}

/// 底部常驻追问栏（静态壳；多轮对话留给后续 session B）。
class _AskBar extends StatelessWidget {
  const _AskBar();

  @override
  Widget build(BuildContext context) {
    final gm = context.gm;
    final l10n = AppLocalizations.of(context)!;
    return Container(
      decoration: BoxDecoration(
        color: gm.bg,
        border: Border(top: BorderSide(color: gm.line)),
      ),
      child: SafeArea(
        top: false,
        child: Padding(
          padding: const EdgeInsets.fromLTRB(20, 9, 20, 14),
          child: Row(children: [
            Expanded(
              child: Container(
                height: 44,
                alignment: Alignment.centerLeft,
                padding: const EdgeInsets.symmetric(horizontal: 15),
                decoration: BoxDecoration(
                    color: gm.surface, border: Border.all(color: gm.line)),
                child: Text(l10n.guideAskPlaceholder,
                    style: GmText.sans(size: 13, color: gm.faint)),
              ),
            ),
            const SizedBox(width: 9),
            Container(
              width: 44,
              height: 44,
              decoration:
                  BoxDecoration(color: gm.ctaBg, shape: BoxShape.circle),
              alignment: Alignment.center,
              child: GmIcon(GmIcons.mic, size: 18, color: gm.ctaInk),
            ),
          ]),
        ),
      ),
    );
  }
}

// ---------------------------------------------------------------------------
// Wall label: single-line flowing, no field labels (notes #10)
// ---------------------------------------------------------------------------

class _WallLabel extends StatelessWidget {
  const _WallLabel({required this.facts});
  final ObjectFacts facts;

  @override
  Widget build(BuildContext context) {
    final gm = context.gm;

    // Truncate medium if overly long (>14 chars)
    String? medium = facts.medium;
    if (medium != null && medium.length > 14) {
      medium = '${medium.substring(0, 12)}…';
    }

    final parts = <String>[
      if (facts.artist?.isNotEmpty == true) facts.artist!,
      if (facts.date?.isNotEmpty == true) facts.date!,
      if (medium?.isNotEmpty == true) medium!,
      if (facts.dimensions?.isNotEmpty == true) facts.dimensions!,
    ];

    if (parts.isEmpty) return const SizedBox.shrink();

    return Text(
      parts.join(' · '),
      style: GmText.sans(size: 12.5, color: gm.sub),
      maxLines: 2,
      overflow: TextOverflow.ellipsis,
    );
  }
}

// ---------------------------------------------------------------------------
// Facts accordion: ▸ 作品信息 (default collapsed) → full table
// ---------------------------------------------------------------------------

class _FactsAccordion extends StatelessWidget {
  const _FactsAccordion({
    required this.facts,
    required this.expanded,
    required this.onToggle,
  });

  final ObjectFacts facts;
  final bool expanded;
  final VoidCallback onToggle;

  @override
  Widget build(BuildContext context) {
    final gm = context.gm;
    final info = AppLocalizations.of(context)!.guideInfo;

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        GestureDetector(
          onTap: onToggle,
          behavior: HitTestBehavior.opaque,
          child: Padding(
            padding: const EdgeInsets.symmetric(vertical: 8),
            child: Row(children: [
              Text(expanded ? '▾ $info' : '▸ $info',
                  style: GmText.sans(
                      size: 12.5, color: gm.sub, weight: FontWeight.w600)),
            ]),
          ),
        ),
        if (expanded) _FactsTable(facts: facts),
      ],
    );
  }
}

class _FactsTable extends StatelessWidget {
  const _FactsTable({required this.facts});
  final ObjectFacts facts;

  @override
  Widget build(BuildContext context) {
    final gm = context.gm;
    final l10n = AppLocalizations.of(context)!;

    final rows = <_FactRow>[
      if (facts.inventory?.isNotEmpty == true)
        _FactRow(l10n.factInventory, facts.inventory!),
      if (facts.location?.isNotEmpty == true)
        _FactRow(l10n.factLocation, facts.location!),
      if (facts.provenance?.isNotEmpty == true)
        _FactRow(l10n.factProvenance, facts.provenance!),
      if (facts.exhibitions.isNotEmpty)
        _FactRow(l10n.factExhibitions, facts.exhibitions.join('；')),
      if (facts.bibliography.isNotEmpty)
        _FactRow(l10n.factBibliography, facts.bibliography.join('；')),
      if (facts.artistLife?.isNotEmpty == true)
        _FactRow(l10n.factArtist, facts.artistLife!),
    ];

    if (rows.isEmpty) {
      return Padding(
        padding: const EdgeInsets.only(bottom: 8),
        child:
            Text(l10n.factNone, style: GmText.sans(size: 12, color: gm.faint)),
      );
    }

    return Padding(
      padding: const EdgeInsets.only(bottom: 8),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          for (int i = 0; i < rows.length; i++) ...[
            _FactRowWidget(row: rows[i]),
            if (i < rows.length - 1) Container(height: 1, color: gm.line),
          ],
        ],
      ),
    );
  }
}

class _FactRow {
  const _FactRow(this.label, this.value);
  final String label;
  final String value;
}

class _FactRowWidget extends StatelessWidget {
  const _FactRowWidget({required this.row});
  final _FactRow row;

  @override
  Widget build(BuildContext context) {
    final gm = context.gm;
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 6),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          SizedBox(
            width: 64,
            child: Text(row.label,
                style: GmText.sans(size: 11.5, color: gm.faint)),
          ),
          const SizedBox(width: 8),
          Expanded(
            child: Text(row.value, style: GmText.sans(size: 12, color: gm.ink)),
          ),
        ],
      ),
    );
  }
}
