import 'package:cross_file/cross_file.dart';
import 'package:riverpod_annotation/riverpod_annotation.dart';
import 'package:gomuseum_app/features/recognition/data/models/recognize_response.dart';
import 'package:gomuseum_app/features/recognition/presentation/providers/recognition_providers.dart';
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
      {this.phash});
  final List<RecognizedItem> candidates;
  final String? labelText;
  final String? slug;
  final String? phash;
}

/// 未收录：诚实文案 + 引导拍墙签（绝不显示 AI 猜测的名字）。
class RecognitionUnrecognized extends RecognitionState {
  const RecognitionUnrecognized(this.labelText, this.reason, this.slug);
  final String? labelText;
  final String? reason;
  final String? slug;
}

class RecognitionError extends RecognitionState {
  const RecognitionError(this.message);
  final String message;
}

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
      final resp = await ds.recognize(
          slug: slug,
          image: image,
          language: language,
          mode: mode,
          deviceId: deviceId);
      state = switch (resp.outcome) {
        RecognizeOutcome.match when resp.match?.isValid == true =>
          RecognitionMatched(resp.match!, slug),
        RecognizeOutcome.candidates when resp.candidates.isNotEmpty =>
          RecognitionCandidates(resp.candidates, resp.labelText, slug,
              phash: resp.phash),
        _ => RecognitionUnrecognized(resp.labelText, resp.reason, slug),
      };
    } catch (_) {
      state = const RecognitionError('recognize_failed');
    }
  }

  /// 确认卡点选「这一件」→ 把「照片→qid」人工确认标注回传后端（喂 CLIP 校准）。
  /// 仅候选态（人真的点了才算确认；match 自动跳转不是人工确认，不上报）。
  /// fire-and-forget：无 phash（老后端）静默跳过；异常在 datasource 内吞掉，绝不打扰跳转。
  void confirmRecognition(String qid) {
    final s = state;
    final phash = s is RecognitionCandidates ? s.phash : null;
    if (phash == null) return;
    ref
        .read(recognitionRemoteDataSourceProvider)
        .confirm(phash: phash, qid: qid);
  }

  /// 候选卡「都不是」→ 转未收录 UI（保留已识别的墙签文字）。
  void rejectCandidates() {
    final s = state;
    if (s is RecognitionCandidates) {
      state = RecognitionUnrecognized(s.labelText, 'rejected', s.slug);
    }
  }

  void resetState() => state = const RecognitionInitial();
}
