import 'dart:async' hide TimeoutException;

import 'package:cross_file/cross_file.dart';
import 'package:flutter/widgets.dart';
import 'package:riverpod_annotation/riverpod_annotation.dart';
import 'package:gomuseum_app/core/error/exceptions.dart';
import 'package:gomuseum_app/features/history/presentation/providers/history_providers.dart';
import 'package:gomuseum_app/features/recognition/data/models/recognize_response.dart';
import 'package:gomuseum_app/features/recognition/presentation/providers/recognition_providers.dart';
import 'package:gomuseum_app/features/payment/data/entitlements.dart';
import 'package:gomuseum_app/features/payment/presentation/providers/benefits_provider.dart';

part 'recognition_provider.g.dart';

/// 识别状态（接地识别三档 outcome + 加载/错误）。
sealed class RecognitionState {
  const RecognitionState();
}

class RecognitionInitial extends RecognitionState {
  const RecognitionInitial();
}

class RecognitionLoading extends RecognitionState {
  const RecognitionLoading();
}

/// 命中：直接跳该 qid 详情。
class RecognitionMatched extends RecognitionState {
  const RecognitionMatched(this.match, this.slug);
  final RecognizedItem match;
  final String? slug;
}

/// 多候选：确认卡「是这件吗？」。
class RecognitionCandidates extends RecognitionState {
  const RecognitionCandidates(this.candidates, this.labelText, this.slug,
      {this.phash, this.photoFeedback = false});
  final List<RecognizedItem> candidates;
  final String? labelText;
  final String? slug;
  final String? phash;

  /// S5 服务端开关(见 RecognizeResponse.photoFeedback)。
  final bool photoFeedback;
}

/// 未收录：诚实文案 + 引导拍墙签（绝不显示 AI 猜测的名字）。
class RecognitionUnrecognized extends RecognitionState {
  const RecognitionUnrecognized(this.labelText, this.reason, this.slug,
      {this.phash, this.photoFeedback = false});
  final String? labelText;
  final String? reason;
  final String? slug;

  /// 这张照片的感知哈希(S4:选择页搜到作品时用它回传「照片=这件」)。老后端没有 → null。
  final String? phash;

  /// S5 服务端开关(见 RecognizeResponse.photoFeedback)。
  final bool photoFeedback;
}

/// 免费额度用尽(后端 402)：不是失败，是该弹付费墙。
class RecognitionQuotaExceeded extends RecognitionState {
  const RecognitionQuotaExceeded({this.passId, this.museum});

  /// 402 带回的撞墙那家馆(slug;前置闸撞墙时 null)。
  final String? museum;

  /// 402 带回的「这家馆该买的票」(命中后才撞墙时有;前置闸撞墙时还不知道馆 → null,
  /// 权益页列出全部可买的票)。
  final String? passId;
}

class RecognitionError extends RecognitionState {
  const RecognitionError(this.message);
  final String message;
}

/// 等到 App 回到前台(S2:后台里失败的请求,切回来再重发)。测试里覆盖成立即返回。
final foregroundWaiterProvider =
    Provider<Future<void> Function()>((ref) => untilAppResumed);

Future<void> untilAppResumed() {
  final s = WidgetsBinding.instance.lifecycleState;
  if (s == null || s == AppLifecycleState.resumed) return Future.value();
  final done = Completer<void>();
  late final AppLifecycleListener listener;
  listener = AppLifecycleListener(onResume: () {
    listener.dispose();
    // 刚回前台时系统网络常常还没恢复(真机 V53 实测重发要发出去):等一下再发。
    // ponytail: 固定 1s;仍常见回前台即失败时改成「等连通性就绪」。
    Future<void>.delayed(resumeSettleDelay).then((_) => done.complete());
  });
  return done.future;
}

/// 回前台后等网络恢复的时间(测试可调)。
@visibleForTesting
Duration resumeSettleDelay = const Duration(seconds: 1);

/// 网络类失败时用同一张照片最多重发几次(总共发 1 + 3 次)。
const _maxResends = 3;

/// 值得用同一张照片重发的失败:超时、断连、网关 5xx(数据源已映射成 NetworkException)。
bool _isTransient(Object e) => e is TimeoutException || e is NetworkException;

/// 识别状态管理 Provider。
@riverpod
class RecognitionNotifier extends _$RecognitionNotifier {
  @override
  RecognitionState build() => const RecognitionInitial();

  /// 接地识别：走新端点，按 outcome 落三档状态。
  /// [mode] = `artwork`（默认）或 `label`（引导补拍墙签）。
  Future<void> recognize({
    String? slug,
    required XFile image,
    required String language,
    String mode = 'artwork',
  }) async {
    state = const RecognitionLoading();
    try {
      final ds = ref.read(recognitionRemoteDataSourceProvider);
      // 恒带 device_id（契约身份回退）：游客设备绑定，令牌抽风时后端仍认得出。
      // deviceIdProvider 自带兜底（不会抛），拿不到就传 null，服务端退回 Bearer。
      String? deviceId;
      try {
        deviceId = await ref.read(deviceIdProvider.future);
      } catch (_) {
        deviceId = null;
      }
      final waitForeground = ref.read(foregroundWaiterProvider);
      Future<RecognizeResponse> send() => ds.recognize(
          slug: slug,
          image: image,
          language: language,
          mode: mode,
          deviceId: deviceId);
      // S2 失败即重发:锁屏/切后台时系统会不会断连,代码里判断不了、各厂商也不同,
      // 两种情况都兜住。同一张照片 → 服务端同键在途合并或缓存命中,不重算不重复扣。
      // 最多重发 [_maxResends] 次(V54 真机:切回来那一刻 Wi‑Fi ↔ 运营商网络切换,
      // 第一次重发途中又被掐断);每次先等回前台(后台网络多半还不通)。
      RecognizeResponse resp;
      for (var attempt = 0;; attempt++) {
        try {
          resp = await send();
          break;
        } catch (e) {
          if (!_isTransient(e) || attempt >= _maxResends) rethrow;
          await waitForeground();
        }
      }
      state = switch (resp.outcome) {
        RecognizeOutcome.match when resp.match?.isValid == true =>
          RecognitionMatched(resp.match!, slug),
        RecognizeOutcome.candidates when resp.candidates.isNotEmpty =>
          RecognitionCandidates(resp.candidates, resp.labelText, slug,
              phash: resp.phash, photoFeedback: resp.photoFeedback),
        _ => RecognitionUnrecognized(resp.labelText, resp.reason, slug,
            phash: resp.phash, photoFeedback: resp.photoFeedback),
      };
      if (state is RecognitionMatched) _refreshFootprints();
    } on QuotaExceededException catch (e) {
      state = RecognitionQuotaExceeded(passId: e.passId, museum: e.museum);
    } catch (_) {
      state = const RecognitionError('recognize_failed');
    }
  }

  /// 确认卡点选「这一件」→ 把「照片→qid」人工确认标注回传后端（喂 CLIP 校准），
  /// **并由后端在那一刻扣 1 次额度**（候选态的唯一扣费点，2026-09-20 改）。
  /// 仅候选态（人真的点了才算确认；match 自动跳转不是人工确认，不上报也不在这扣）。
  /// fire-and-forget：无 phash（老后端）静默跳过；异常在 datasource 内吞掉，绝不打扰跳转。
  ///
  /// ⚠️ 刷新权益放在 notifier 里而不是调用方：调用方（相机页）确认完立刻
  /// pushReplacement 走人，await 回来时它的 ref 已经 dispose 了。
  ///
  /// [fromSearch](S4):选择页搜到的作品 = 用户告诉我们「这张照片是这件」。
  /// 只记答案,后端不计费(`source=search`),所以也不用刷权益。
  ///
  /// [phashOverride](S5):拍过说明牌时,答案属于先前那张**作品照片**,不是说明牌照片。
  Future<void> confirmRecognition(String qid,
      {bool fromSearch = false, String? phashOverride}) async {
    final s = state;
    final phash = phashOverride ??
        switch (s) {
          RecognitionCandidates() => s.phash,
          RecognitionUnrecognized() when fromSearch => s.phash,
          _ => null,
        };
    if (phash == null) return;
    await ref
        .read(recognitionRemoteDataSourceProvider)
        .confirm(phash: phash, qid: qid, source: fromSearch ? 'search' : null);
    if (fromSearch) return; // 没扣次:不用刷权益;足迹下次刷新时自然带上
    _refreshFootprints(); // 放在权益刷新之前:那边抛了不该连带足迹
    // 确认扣掉了 1 次额度，权益缓存必须失效 —— 否则设置页还显示旧的剩余次数。
    ref.invalidate(entitlementsProvider);
    ref.invalidate(museumEntitlementsProvider);
    await ref.read(benefitsStateProvider.notifier).refresh();
  }

  /// 命中 / 点选确认 = 后端多了一条足迹。足迹列表(足迹 tab + 首页「继续游览」)
  /// 是常驻缓存,不在这里刷的话一直停在打开 App 那一刻(2026-10-02 真机报告:
  /// 连拍几十件,两处都看不到)。用 refresh 而不是 invalidate:后者会先清空列表,
  /// 首页那节闪没再出现。
  void _refreshFootprints() =>
      unawaited(ref.read(historyProvider.notifier).refresh());

  /// 候选卡「都不是」→ 转未收录 UI（保留已识别的墙签文字），并把这组候选上报为被否定(S3)。
  void rejectCandidates() {
    final s = state;
    if (s is RecognitionCandidates) {
      final phash = s.phash;
      if (phash != null) {
        unawaited(ref
            .read(recognitionRemoteDataSourceProvider)
            .reject(phash: phash, qids: [for (final c in s.candidates) c.qid]));
      }
      state = RecognitionUnrecognized(s.labelText, 'rejected', s.slug,
          phash: s.phash, photoFeedback: s.photoFeedback);
    }
  }

  void resetState() => state = const RecognitionInitial();
}
