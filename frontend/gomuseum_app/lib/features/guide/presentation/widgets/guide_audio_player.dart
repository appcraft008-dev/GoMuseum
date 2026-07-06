/// 讲解音频播放器：点播放→懒取 TTS（首次现场生成 ~数秒）→播放；
/// 语速 0.75/1/1.5/2x（客户端 setSpeed，零后端成本）；404「讲解生成后可听」/503「暂不可用可重试」。
library;

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

enum _Ui { idle, loading, loaded, notReady, error }

class GuideAudioPlayer extends ConsumerStatefulWidget {
  const GuideAudioPlayer({
    super.key,
    required this.slug,
    required this.qid,
    required this.language,
    this.initialUrl,
  });

  final String slug;
  final String qid;

  /// API 语言参数（繁体已是 zh-hant）。
  final String language;

  /// 后端已预生成的音频直链（有则直接用，免懒取）。
  final String? initialUrl;

  @override
  ConsumerState<GuideAudioPlayer> createState() => _GuideAudioPlayerState();
}

class _GuideAudioPlayerState extends ConsumerState<GuideAudioPlayer> {
  final AudioPlayer _player = AudioPlayer();
  _Ui _ui = _Ui.idle;

  static const List<double> _speeds = [1.0, 1.5, 2.0, 0.75];
  int _speedIdx = 0;

  @override
  void dispose() {
    _player.dispose();
    super.dispose();
  }

  Future<void> _onTap() async {
    // 已加载 → 播放/暂停切换（结束则从头）。
    if (_ui == _Ui.loaded) {
      if (_player.playing) {
        await _player.pause();
      } else {
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
      final res = await ref.read(catalogDataSourceProvider).getGuideAudio(
            slug: widget.slug,
            qid: widget.qid,
            language: widget.language,
          );
      if (!mounted) return;
      switch (res) {
        case GuideAudioReady(:final url):
          src = url;
        case GuideAudioNotReady():
          setState(() => _ui = _Ui.notReady);
          return;
        case GuideAudioFailed():
          setState(() => _ui = _Ui.error);
          return;
      }
    }

    try {
      await _player.setUrl(src);
      await _player.setSpeed(_speeds[_speedIdx]);
      if (!mounted) return;
      setState(() => _ui = _Ui.loaded);
      await _player.play();
    } catch (_) {
      if (mounted) setState(() => _ui = _Ui.error);
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
        return l10n.guideListen;
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
          Expanded(
            child: Text(_label(l10n),
                style: GmText.sans(size: 12, color: gm.sub, letterSpacing: 0.4),
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
