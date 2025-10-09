import 'package:gomuseum_app/features/explanation/data/models/explanation_model.dart';

/// 解释功能远程数据源接口
///
/// 定义与后端API交互的抽象方法。
/// 遵循依赖倒置原则，由具体实现类处理HTTP请求细节。
abstract class ExplanationRemoteDataSource {
  /// 生成艺术品解释
  ///
  /// [artworkName] 艺术品名称（必需）
  /// [language] 语言代码（必需）：en, fr, de, es, it, zh
  /// [detailLevel] 详细程度（可选，默认'standard'）：brief, standard, detailed
  /// [includeAudio] 是否生成音频（可选，默认false）
  /// [recognitionId] 关联的识别记录ID（可选）
  ///
  /// 返回 [ExplanationModel] 解释数据模型
  ///
  /// 可能抛出的异常：
  /// - [ServerException] 服务器错误（500）
  /// - [NetworkException] 网络连接失败
  /// - [ValidationException] 请求参数验证失败（400）
  /// - [TimeoutException] 请求超时
  Future<ExplanationModel> generateExplanation({
    required String artworkName,
    required String language,
    String detailLevel = 'standard',
    bool includeAudio = false,
    String? recognitionId,
  });

  /// 根据ID获取解释记录
  ///
  /// [id] 解释记录的唯一标识符
  ///
  /// 返回 [ExplanationModel] 解释数据模型
  ///
  /// 可能抛出的异常：
  /// - [NotFoundException] 记录不存在（404）
  /// - [ServerException] 服务器错误（500）
  /// - [NetworkException] 网络连接失败
  /// - [TimeoutException] 请求超时
  Future<ExplanationModel> getExplanationById(String id);

  /// 获取艺术品的所有解释记录（多语言）
  ///
  /// [artworkName] 艺术品名称
  ///
  /// 返回 `List<ExplanationModel>` 解释列表（可能为空）
  ///
  /// 可能抛出的异常：
  /// - [ServerException] 服务器错误（500）
  /// - [NetworkException] 网络连接失败
  /// - [TimeoutException] 请求超时
  Future<List<ExplanationModel>> getExplanationsByArtwork(String artworkName);
}
