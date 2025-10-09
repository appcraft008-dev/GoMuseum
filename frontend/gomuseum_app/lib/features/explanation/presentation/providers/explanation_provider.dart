import 'package:freezed_annotation/freezed_annotation.dart';
import 'package:riverpod_annotation/riverpod_annotation.dart';
import 'package:gomuseum_app/features/explanation/domain/entities/explanation.dart';
import 'package:gomuseum_app/features/explanation/domain/usecases/generate_explanation.dart';
import 'package:gomuseum_app/features/explanation/presentation/providers/explanation_providers.dart';

part 'explanation_provider.freezed.dart';
part 'explanation_provider.g.dart';

/// 解释功能状态类
///
/// 使用Freezed实现不可变状态模式，支持模式匹配和值比较。
/// 状态流转：initial -> loading -> success/error
@freezed
class ExplanationState with _$ExplanationState {
  /// 初始状态
  ///
  /// 页面首次加载时的默认状态，未发起任何请求。
  const factory ExplanationState.initial() = ExplanationInitial;

  /// 加载中状态
  ///
  /// 正在调用API生成解释，显示加载指示器。
  const factory ExplanationState.loading() = ExplanationLoading;

  /// 成功状态
  ///
  /// API调用成功，包含生成的解释数据。
  /// [explanation] 完整的解释实体，包含内容、音频等信息
  const factory ExplanationState.success(Explanation explanation) = ExplanationSuccess;

  /// 错误状态
  ///
  /// API调用失败或参数验证失败，包含错误信息。
  /// [message] 用户可读的错误描述
  const factory ExplanationState.error(String message) = ExplanationError;
}

/// 解释功能状态管理Notifier
///
/// 负责处理解释生成的业务逻辑和状态转换。
/// 使用Riverpod的NotifierProvider模式，支持自动依赖注入。
@riverpod
class ExplanationNotifier extends _$ExplanationNotifier {
  @override
  ExplanationState build() {
    // 初始化为initial状态
    return const ExplanationState.initial();
  }

  /// 生成艺术品解释
  ///
  /// 调用UseCase执行解释生成逻辑，并更新状态。
  ///
  /// 参数：
  /// - [artworkName] 艺术品名称（必需）
  /// - [language] 语言代码（必需）：en, fr, de, es, it, zh
  /// - [detailLevel] 详细程度（可选，默认'standard'）：brief, standard, detailed
  /// - [includeAudio] 是否生成音频（可选，默认false）
  /// - [recognitionId] 关联的识别记录ID（可选）
  ///
  /// 状态流转：
  /// 1. 设置为loading状态
  /// 2. 调用UseCase生成解释
  /// 3. 成功：设置为success状态，包含Explanation
  /// 4. 失败：设置为error状态，包含错误信息
  Future<void> generateExplanation({
    required String artworkName,
    required String language,
    String detailLevel = 'standard',
    bool includeAudio = false,
    String? recognitionId,
  }) async {
    // 1. 设置加载状态
    state = const ExplanationState.loading();

    // 2. 创建UseCase参数
    final params = GenerateExplanationParams(
      artworkName: artworkName,
      language: language,
      detailLevel: detailLevel,
      includeAudio: includeAudio,
      recognitionId: recognitionId,
    );

    // 3. 调用UseCase执行业务逻辑
    final useCase = ref.read(generateExplanationUseCaseProvider);
    final result = await useCase(params);

    // 4. 根据结果更新状态
    result.fold(
      // Left: 失败，设置错误状态
      (failure) {
        state = ExplanationState.error(failure.message);
      },
      // Right: 成功，设置成功状态
      (explanation) {
        state = ExplanationState.success(explanation);
      },
    );
  }

  /// 重置状态为初始状态
  ///
  /// 用于清空当前解释数据，返回初始页面。
  void reset() {
    state = const ExplanationState.initial();
  }
}
