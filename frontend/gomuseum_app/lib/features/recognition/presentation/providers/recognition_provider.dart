import 'package:cross_file/cross_file.dart';
import 'package:riverpod_annotation/riverpod_annotation.dart';
import 'package:gomuseum_app/features/recognition/data/models/recognize_response.dart';
import 'package:gomuseum_app/features/recognition/presentation/providers/recognition_providers.dart';

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
  final String slug;
}

/// 多候选：确认卡「是这件吗？」。
class RecognitionCandidates extends RecognitionState {
  const RecognitionCandidates(this.candidates, this.labelText, this.slug);
  final List<RecognizedItem> candidates;
  final String? labelText;
  final String slug;
}

/// 未收录：诚实文案 + 引导拍墙签（绝不显示 AI 猜测的名字）。
class RecognitionUnrecognized extends RecognitionState {
  const RecognitionUnrecognized(this.labelText, this.reason, this.slug);
  final String? labelText;
  final String? reason;
  final String slug;
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
    required String slug,
    required XFile image,
    required String language,
    String mode = 'artwork',
  }) async {
    state = const RecognitionLoading();
    try {
      final ds = ref.read(recognitionRemoteDataSourceProvider);
      final resp = await ds.recognize(
          slug: slug, image: image, language: language, mode: mode);
      state = switch (resp.outcome) {
        RecognizeOutcome.match when resp.match?.isValid == true =>
          RecognitionMatched(resp.match!, slug),
        RecognizeOutcome.candidates when resp.candidates.isNotEmpty =>
          RecognitionCandidates(resp.candidates, resp.labelText, slug),
        _ => RecognitionUnrecognized(resp.labelText, resp.reason, slug),
      };
    } catch (_) {
      state = const RecognitionError('recognize_failed');
    }
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
