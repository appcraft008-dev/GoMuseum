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
import 'package:gomuseum_app/features/auth/presentation/auth_provider.dart';
import 'package:gomuseum_app/features/payment/data/entitlements.dart';
import 'package:gomuseum_app/features/payment/presentation/widgets/paywall_sheet.dart';
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
    this.autoPlay = false,
    this.section = 'guide',
    this.qaSort,
    this.label,
  });

  final String slug;
  final String qid;

  /// 识别成功后自动播。**只在这一件确实能放时才自动播** ——
  /// 免费用户的第二件自动弹付费墙 = 一进页面就被推销,最差的体验。
  final bool autoPlay;

  /// API 语言参数（繁体已是 zh-hant）。
  final String language;

  /// 段落：guide / 深度模块 section_code / qa / artist_bio。
  final String section;

  /// section=qa 时必传（问答定位键）。
  final int? qaSort;

  /// 后端已预生成的音频直链（有则直接用，免懒取）。

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

  /// 同一件内只轻提示一次:再点才升级到完整付费页(三档强度,避免反复打扰)。
  static final Set<String> _hintedQids = <String>{};

  /// 撞墙时的分档反应。返回 true 表示已拦下(调用方不要继续播)。
  ///
  /// ⚠️ 已购未激活的用户要先走激活确认,不能直接弹付费墙——他已经付过钱了,
  /// 再让他看购买页是最糟的体验。买了不立即计时是有意设计,这里是它的触发器。
  Future<bool> _blockedByPaywall() async {
    final ent = ref.read(entitlementsProvider).value;
    if (ent == null || ent.canPlayAudio(widget.qid)) return false;

    if (ent.isPurchasedNotActivated) {
      if (await ensurePassActivated(context, ref, ent)) return false; // 已生效,继续播
      if (mounted) setState(() => _ui = _Ui.idle);
      return true; // 用户选了"再等等"
    }

    if (_hintedQids.add(widget.qid)) {
      showPaywallHint(context);
    } else {
      showPaywallSheet(context, reason: 'audio');
    }
    if (mounted) setState(() => _ui = _Ui.idle);
    return true;
  }

  bool _autoPlayed = false;

  /// 自动播的准入:通票内、或这就是免费用户的首件(未认领 / 已认领同一件)。
  /// 拿不到权益时不自动播 —— 宁可不响,也不要一进页面就撞墙。
  void _maybeAutoPlay() {
    if (!widget.autoPlay || _autoPlayed || _ui != _Ui.idle) return;
    final ent = ref.read(entitlementsProvider).value;
    if (ent == null) return;
    final willSucceed = ent.isActive ||
        ent.freeAudioQid == null ||
        ent.freeAudioQid == widget.qid;
    if (!willSucceed) return;
    _autoPlayed = true;
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (mounted) _onTap();
    });
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

    // 付费墙:必须在取音频之前——后端也会拦(402),这里只是免掉一次往返。
    if (await _blockedByPaywall()) return;

    setState(() => _ui = _Ui.loading);

    // ⚠️ 曾有一条"直链快路径":内容接口下发 audio_url 就直接 setUrl。
    // 两个问题:①绕过付费墙闸门 ②那些直链是 P0-b 迁移后的**死链**(实测 404),
    // 而失败不回落懒取、直接置 error —— 预热过的藏品点播放就是坏的。
    // 现在统一走已加闸的 /audio(流式优先,失败回落 legacy)。

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
  /// 客户端权益缓存过期时,前置闸可能放行而后端拒绝——这里保证仍弹墙。
  bool _showPaywallAnyway() {
    ref.invalidate(entitlementsProvider); // 顺便刷新,下次判断就准了
    showPaywallSheet(context, reason: 'audio');
    return true;
  }

  /// 这一件是不是用掉了(或将要用掉)免费名额——通票用户不显示此标。
  bool _isFreePreview() {
    final ent = ref.watch(entitlementsProvider).value;
    if (ent == null || ent.isActive) return false;
    return ent.freeAudioQid == null || ent.freeAudioQid == widget.qid;
  }

  Future<Map<String, String>> _authHeaders() async {
    final token = await ref.read(authRepositoryProvider).getAccessToken();
    return token == null ? const {} : {'Authorization': 'Bearer $token'};
  }

  Future<void> _loadStreaming() async {
    final url = ref.read(catalogDataSourceProvider).audioStreamUrl(
          slug: widget.slug,
          qid: widget.qid,
          language: widget.language,
          section: widget.section,
        );
    try {
      // ⚠️ setUrl 由系统播放器直取,**不经 Dio 拦截器**,得自己带令牌;
      // 否则音频端点加鉴权后流式全 401。令牌过期也不致命:401 → 落回
      // legacy 路径(走 Dio,会自动刷新),只是慢一点。
      await _player.setUrl(url, headers: await _authHeaders());
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
        case GuideAudioPassRequired():
          setState(() => _ui = _Ui.idle);
          // 后端才是付费墙的执行点:客户端闸放行了但后端拒了(权益已变/被绕过)
          if (!await _blockedByPaywall()) _showPaywallAnyway();
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

    // 权益是异步到达的:initState 时通常还没加载完,所以在 build 里试。
    // _maybeAutoPlay 自带一次性与准入判断,重复调用无副作用。
    _maybeAutoPlay();

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
          // 「免费试听」必须明说 —— 否则用户随手在一件小作品上用掉名额,
          // 走到蒙娜丽莎前发现锁了会觉得被坑(见 memory monetization-plan)。
          if (_isFreePreview()) ...[
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
              decoration: BoxDecoration(border: Border.all(color: gm.faint)),
              child: Text(l10n.audioFreePreview,
                  style: GmText.sans(size: 10, color: gm.sub)),
            ),
            const SizedBox(width: 8),
          ],
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
