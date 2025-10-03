import 'dart:io';
import 'package:riverpod_annotation/riverpod_annotation.dart';
import '../../domain/entities/recognition_result.dart';
import 'recognition_providers.dart';

part 'recognition_provider.g.dart';

/// 识别状态
sealed class RecognitionState {
  const RecognitionState();
}

/// 初始状态
class RecognitionInitial extends RecognitionState {
  const RecognitionInitial();
}

/// 加载中状态
class RecognitionLoading extends RecognitionState {
  const RecognitionLoading();
}

/// 成功状态
class RecognitionSuccess extends RecognitionState {
  final RecognitionResult result;

  const RecognitionSuccess(this.result);
}

/// 错误状态
class RecognitionError extends RecognitionState {
  final String message;

  const RecognitionError(this.message);
}

/// 识别状态管理Provider
@riverpod
class RecognitionNotifier extends _$RecognitionNotifier {
  @override
  RecognitionState build() {
    return const RecognitionInitial();
  }

  /// 识别艺术品
  Future<void> recognizeArtwork(File imageFile) async {
    state = const RecognitionLoading();

    final useCase = ref.read(recognizeArtworkUseCaseProvider);
    final result = await useCase(imageFile);

    result.fold(
      (failure) => state = RecognitionError(failure.message),
      (recognition) => state = RecognitionSuccess(recognition),
    );
  }

  /// 重置状态
  void resetState() {
    state = const RecognitionInitial();
  }
}
