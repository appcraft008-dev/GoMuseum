/// 段落音频播放器：点播放→懒取 TTS（首次现场生成 ~数秒）→播放。
/// 覆盖 guide/深度模块/问答(qa+qaSort)/作者介绍(artist_bio)。
/// 语速 0.75/1/1.5/2x（客户端 setSpeed，零后端成本）；加载后显进度条+剩余时间。
/// 409「生成中」静默转圈自动重试（≤30s）；404「讲解生成后可听」；503「暂不可用可重试」。
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
    String? src = widget.initialUrl;
    if (src == null || src.isEmpty) {
      src = await _fetchWithRetry();
      if (src == null) return; // 状态已在 _fetchWithRetry 内置为 notReady/error
    }

    try {
      await _player.setUrl(src);
      await _player.setSpeed(_speeds[_speedIdx]);
      if (!mounted) return;
      setState(() => _ui = _Ui.loaded);
      _ActiveAudio.takeOver(this);
      await _player.play();
    } catch (_) {
      if (mounted) setState(() => _ui = _Ui.error);
    }
  }

  /// 懒取音频；409（生成中）静默等 2s 自动重试，上限 ~30s；返回 null 表示已置终态。
  Future<String?> _fetchWithRetry() async {
    final deadline = DateTime.now().add(const Duration(seconds: 30));
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
          await Future.delayed(const Duration(seconds: 2));
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

  /// 进度条 + 剩余时间（-1:23）；剩余按当前语速换算真实等待。
  Widget _progress(GmPalette gm) {
    return StreamBuilder<Duration>(
      stream: _player.positionStream,
      builder: (_, posSnap) {
        final pos = posSnap.data ?? Duration.zero;
        final dur = _player.duration ?? Duration.zero;
        final total = dur.inMilliseconds;
        final frac =
            total == 0 ? 0.0 : (pos.inMilliseconds / total).clamp(0.0, 1.0);
        final rate = _speeds[_speedIdx];
        final remainMs =
            ((dur - pos).inMilliseconds / rate).round().clamp(0, 1 << 31);
        return Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            SizedBox(
              height: 3,
              child: Stack(children: [
                Container(color: gm.line),
                FractionallySizedBox(
                  widthFactor: frac,
                  child: Container(color: gm.accent),
                ),
              ]),
            ),
            const SizedBox(height: 4),
            Align(
              alignment: Alignment.centerRight,
              child: Text('-${_fmt(remainMs)}',
                  style: GmText.sans(size: 10.5, color: gm.sub)),
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
