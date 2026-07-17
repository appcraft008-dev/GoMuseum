/// 段落音频播放器：点播放→懒取 TTS（首次现场生成 ~数秒）→播放。
/// 覆盖 guide/深度模块/问答(qa+qaSort)/作者介绍(artist_bio)。
/// guide+深度段：/audio/stream URL 直接 setUrl 给系统播放器（原生 chunked MP3
/// 直播流路径，边生成边播）；非音频响应(缓存 JSON/409/404)→播放器报错→回退老 /audio。
/// 流式起播有看门狗：position 不推进(静音/卡死)即回退老 /audio，保证可靠出声。
/// qa 连念/作者介绍仍走老 /audio（后端 v1 不支持流式）。
/// 语速 0.75/1/1.5/2x（客户端 setSpeed，零后端成本）；加载后显进度条+剩余时间。
/// 409「生成中」静默转圈指数退避重试（2→4→8→16s，≤60s）；404「讲解生成后可听」；503「暂不可用可重试」。
library;

import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:gomuseum_app/features/content/data/models/guide_audio.dart';
import 'package:gomuseum_app/features/content/presentation/providers/catalog_providers.dart';
import 'package:gomuseum_app/l10n/app_localizations.dart';
import 'package:gomuseum_app/theme/gm_palette.dart';
import 'package:gomuseum_app/theme/gm_theme_x.dart';
import 'package:gomuseum_app/theme/gm_tokens.dart';
import 'package:gomuseum_app/ui/gm/gm_icon.dart';
import 'package:just_audio/just_audio.dart';

/// 单实例播放：同屏任一 player 开播前先停上一个正在播的（问答可同时展开多条）。
class _ActiveAudio {
  static _GuideAudioPlayerState? _current;
  static void takeOver(_GuideAudioPlayerState next) {
    if (_current != null && !identical(_current, next)) _current!._pauseQuiet();
    _current = next;
  }

  static void release(_GuideAudioPlayerState self) {
    if (identical(_current, self)) _current = null;
  }
}

enum _Ui { idle, loading, loaded, notReady, error }

class GuideAudioPlayer extends ConsumerStatefulWidget {
  const GuideAudioPlayer({
    super.key,
    required this.slug,
    required this.qid,
    required this.language,
    this.section = 'guide',
    this.qaSort,
    this.initialUrl,
    this.label,
  });

  final String slug;
  final String qid;

  /// API 语言参数（繁体已是 zh-hant）。
  final String language;

  /// 段落：guide / 深度模块 section_code / qa / artist_bio。
  final String section;

  /// section=qa 时必传（问答定位键）。
  final int? qaSort;

  /// 后端已预生成的音频直链（有则直接用，免懒取）。
  final String? initialUrl;

  /// idle 态按钮文案（默认「听讲解」）。
  final String? label;

  @override
  ConsumerState<GuideAudioPlayer> createState() => _GuideAudioPlayerState();
}

class _GuideAudioPlayerState extends ConsumerState<GuideAudioPlayer> {
  final AudioPlayer _player = AudioPlayer();
  _Ui _ui = _Ui.idle;

  static const List<double> _speeds = [1.0, 1.5, 2.0, 0.75];
  int _speedIdx = 0;

  /// 流式端点仅 guide + canonical 深度段；qa 连念/作者介绍仍走老 /audio。
  bool get _useStream =>
      widget.section != 'qa' && widget.section != 'artist_bio';

  void _pauseQuiet() {
    if (_player.playing) _player.pause();
  }

  @override
  void dispose() {
    _ActiveAudio.release(this);
    _player.dispose();
    super.dispose();
  }

  Future<void> _onTap() async {
    // 已加载 → 播放/暂停切换（结束则从头）。
    if (_ui == _Ui.loaded) {
      if (_player.playing) {
        await _player.pause();
      } else {
        _ActiveAudio.takeOver(this);
        if (_player.processingState == ProcessingState.completed) {
          await _player.seek(Duration.zero);
        }
        await _player.play();
      }
      return;
    }

    setState(() => _ui = _Ui.loading);

    // 后端已预生成的直链 → 直接播（免懒取/免流式）。
    final initial = widget.initialUrl;
    if (initial != null && initial.isNotEmpty) {
      if (!await _startWith(() => _player.setUrl(initial))) {
        if (mounted) setState(() => _ui = _Ui.error);
      }
      return;
    }

    if (_useStream) {
      await _loadStreaming();
    } else {
      await _loadLegacy();
    }
  }

  /// 设源→设速→播；成功返回 true。失败不置 UI（由调用方决定报错或回退）。
  Future<bool> _startWith(Future<void> Function() setSource) async {
    try {
      await setSource();
      await _player.setSpeed(_speeds[_speedIdx]);
      if (!mounted) return false;
      setState(() => _ui = _Ui.loaded);
      _ActiveAudio.takeOver(this);
      await _player.play();
      return true;
    } catch (_) {
      return false;
    }
  }

  /// 出声=播放位置推进（just_audio 仅在 ExoPlayer 真 READY 时外推 position，
  /// 不会被 buffering 骗）。窗口内越过阈值→成功；到点仍不动→判失败(回退)。
  Future<bool> _playbackStarted(Duration window) async {
    final deadline = DateTime.now().add(window);
    while (mounted && DateTime.now().isBefore(deadline)) {
      if (_player.position > const Duration(milliseconds: 300)) return true;
      if (_player.processingState == ProcessingState.completed) {
        return _player.position > Duration.zero;
      }
      await Future.delayed(const Duration(milliseconds: 250));
    }
    return false;
  }

  /// 409「生成中」重试退避：2→4→8→16s（封顶）。指数退避消除段级锁 409 风暴
  /// （#262 addendum 根因3：老 2s 固定重试 30s 内连打 15+ 次）。
  static Duration _backoff(int attempt) =>
      Duration(seconds: (2 << attempt).clamp(2, 16));

  /// 流式播放：把 /audio/stream URL 直接交给系统播放器（ExoPlayer/AVPlayer 原生
  /// 支持 chunked MP3 直播流——网络电台同款路径），单次请求、无自定义源无本地 proxy。
  /// 此前经 dio+TtsChunkAudioSource+just_audio proxy 的链路在真机静音——proxy 的
  /// Range 分支对 contentLength=null 空断言崩溃(见 handoff Addendum2/3)，已整体废弃。
  /// 非音频响应(缓存 JSON/409/404)会让播放器快速报错 → 回退老 /audio 分流；
  /// 起播后看门狗兜底(9s position 不动→回退)，永不永久静音。
  Future<void> _loadStreaming() async {
    final url = ref.read(catalogDataSourceProvider).audioStreamUrl(
          slug: widget.slug,
          qid: widget.qid,
          language: widget.language,
          section: widget.section,
        );
    try {
      await _player.setUrl(url); // 预加载：格式就绪即返回（JSON/4xx 在此抛）
      await _player.setSpeed(_speeds[_speedIdx]);
      if (!mounted) return;
      setState(() => _ui = _Ui.loaded);
      _ActiveAudio.takeOver(this);
      unawaited(_player.play().catchError((_) {}));
      if (await _playbackStarted(const Duration(seconds: 9))) return;
    } catch (_) {
      // 落到 legacy
    }
    if (!mounted) return;
    await _player.stop();
    setState(() => _ui = _Ui.loading);
    await _loadLegacy();
  }

  /// 老 /audio 路径（qa/作者介绍常走此；流式失败也回退到此）。
  Future<void> _loadLegacy() async {
    final url = await _fetchWithRetry();
    if (url == null) return; // 终态已在 _fetchWithRetry 内置
    if (!await _startWith(() => _player.setUrl(url))) {
      if (mounted) setState(() => _ui = _Ui.error);
    }
  }

  /// 懒取音频；409（生成中）指数退避自动重试，上限 ~60s；返回 null 表示已置终态。
  Future<String?> _fetchWithRetry() async {
    final deadline = DateTime.now().add(const Duration(seconds: 60));
    var attempt = 0;
    while (true) {
      final res = await ref.read(catalogDataSourceProvider).getGuideAudio(
            slug: widget.slug,
            qid: widget.qid,
            language: widget.language,
            section: widget.section,
            qaSort: widget.qaSort,
          );
      if (!mounted) return null;
      switch (res) {
        case GuideAudioReady(:final url):
          return url;
        case GuideAudioGenerating():
          if (DateTime.now().isAfter(deadline)) {
            setState(() => _ui = _Ui.error);
            return null;
          }
          await Future.delayed(_backoff(attempt++));
          if (!mounted) return null;
          continue; // 保持 loading 转圈，重试
        case GuideAudioNotReady():
          setState(() => _ui = _Ui.notReady);
          return null;
        case GuideAudioFailed():
          setState(() => _ui = _Ui.error);
          return null;
      }
    }
  }

  void _cycleSpeed() {
    setState(() => _speedIdx = (_speedIdx + 1) % _speeds.length);
    _player.setSpeed(_speeds[_speedIdx]);
  }

  String _label(AppLocalizations l10n) {
    switch (_ui) {
      case _Ui.notReady:
        return l10n.audioNotReady;
      case _Ui.error:
        return l10n.audioFailed;
      default:
        return widget.label ?? l10n.guideListen;
    }
  }

  @override
  Widget build(BuildContext context) {
    final gm = context.gm;
    final l10n = AppLocalizations.of(context)!;

    return Container(
      margin: const EdgeInsets.only(top: 11),
      padding: const EdgeInsets.fromLTRB(10, 7, 12, 7),
      decoration: BoxDecoration(
        color: gm.surface,
        border: Border.all(color: gm.line),
      ),
      child: Row(
        children: [
          GestureDetector(
            onTap: _ui == _Ui.loading ? null : _onTap,
            behavior: HitTestBehavior.opaque,
            child: Container(
              width: 27,
              height: 27,
              decoration: BoxDecoration(
                shape: BoxShape.circle,
                border: Border.all(color: gm.accent, width: 1.5),
              ),
              alignment: Alignment.center,
              child: _icon(gm),
            ),
          ),
          const SizedBox(width: 10),
          // 加载后 → 进度条 + 剩余时间；否则文案。
          if (_ui == _Ui.loaded)
            Expanded(child: _progress(gm))
          else
            Expanded(
              child: Text(_label(l10n),
                  style:
                      GmText.sans(size: 12, color: gm.sub, letterSpacing: 0.4),
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis),
            ),
          // 语速档位（加载后可见）。
          if (_ui == _Ui.loaded) ...[
            const SizedBox(width: 8),
            GestureDetector(
              onTap: _cycleSpeed,
              behavior: HitTestBehavior.opaque,
              child: Container(
                padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                decoration: BoxDecoration(
                  border: Border.all(color: gm.line),
                  borderRadius: BorderRadius.circular(999),
                ),
                child: Text('${_speeds[_speedIdx]}x',
                    style: GmText.sans(
                        size: 11, color: gm.accent, weight: FontWeight.w600)),
              ),
            ),
          ],
        ],
      ),
    );
  }

  /// 进度条 + 时间。总时长已知(缓存/R2 或流式下载完)：正常进度条 + 剩余倒计时(-1:23)。
  /// 总时长未知(流式播放中，无 Content-Length)：不确定进度条(扫动) + 已播时间正着走，
  /// 避免卡在 0%/-0:00 假死(#站立的模特反馈)；拿到时长后自动切回倒计时。
  Widget _progress(GmPalette gm) {
    return StreamBuilder<Duration>(
      stream: _player.positionStream,
      builder: (_, posSnap) {
        final pos = posSnap.data ?? Duration.zero;
        final dur = _player.duration;
        final known = dur != null && dur.inMilliseconds > 0;
        final rate = _speeds[_speedIdx];
        return Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            SizedBox(
              height: 3,
              child: known
                  ? Stack(children: [
                      Container(color: gm.line),
                      FractionallySizedBox(
                        widthFactor: (pos.inMilliseconds / dur.inMilliseconds)
                            .clamp(0.0, 1.0),
                        child: Container(color: gm.accent),
                      ),
                    ])
                  : LinearProgressIndicator(
                      backgroundColor: gm.line,
                      color: gm.accent,
                      minHeight: 3,
                    ),
            ),
            const SizedBox(height: 4),
            Align(
              alignment: Alignment.centerRight,
              child: Text(
                known
                    ? '-${_fmt(((dur - pos).inMilliseconds / rate).round().clamp(0, 1 << 31))}'
                    : _fmt(
                        (pos.inMilliseconds / rate).round().clamp(0, 1 << 31)),
                style: GmText.sans(size: 10.5, color: gm.sub),
              ),
            ),
          ],
        );
      },
    );
  }

  static String _fmt(int ms) {
    final s = (ms / 1000).round();
    final m = s ~/ 60;
    return '$m:${(s % 60).toString().padLeft(2, '0')}';
  }

  Widget _icon(GmPalette gm) {
    if (_ui == _Ui.loading) {
      return SizedBox(
        width: 13,
        height: 13,
        child: CircularProgressIndicator(strokeWidth: 1.8, color: gm.accent),
      );
    }
    if (_ui == _Ui.loaded) {
      return StreamBuilder<PlayerState>(
        stream: _player.playerStateStream,
        builder: (_, snap) {
          final playing = snap.data?.playing ?? false;
          final done = snap.data?.processingState == ProcessingState.completed;
          return GmIcon(playing && !done ? GmIcons.pause : GmIcons.play,
              size: 12, color: gm.accent, fill: true);
        },
      );
    }
    return GmIcon(GmIcons.play, size: 12, color: gm.accent, fill: true);
  }
}
