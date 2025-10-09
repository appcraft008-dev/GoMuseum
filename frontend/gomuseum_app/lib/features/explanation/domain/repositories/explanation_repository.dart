import 'package:dartz/dartz.dart';
import 'package:gomuseum_app/core/error/failures.dart';
import 'package:gomuseum_app/features/explanation/domain/entities/explanation.dart';

/// 解释Repository接口（抽象类）
///
/// 定义艺术品解释功能的数据访问接口。
/// 遵循Clean Architecture原则，由Data层实现具体逻辑。
abstract class ExplanationRepository {
  /// 生成艺术品解释
  ///
  /// [artworkName] 艺术品名称（必需）
  /// [language] 语言代码（必需）：en, fr, de, es, it, zh
  /// [detailLevel] 详细程度（可选，默认'standard'）：brief, standard, detailed
  /// [includeAudio] 是否生成音频（可选，默认false）
  /// [recognitionId] 关联的识别记录ID（可选）
  ///
  /// 返回 [Either<Failure, Explanation>]：
  /// - Left(Failure)：请求失败，包含错误信息
  /// - Right(Explanation)：请求成功，返回解释实体
  Future<Either<Failure, Explanation>> generateExplanation({
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
  /// 返回 [Either<Failure, Explanation>]：
  /// - Left(Failure)：查询失败或记录不存在
  /// - Right(Explanation)：查询成功，返回解释实体
  Future<Either<Failure, Explanation>> getExplanationById(String id);

  /// 获取艺术品的所有解释记录（多语言）
  ///
  /// [artworkName] 艺术品名称
  ///
  /// 返回 `Either<Failure, List<Explanation>>`：
  /// - Left(Failure)：查询失败
  /// - Right(List(Explanation))：查询成功，返回解释列表（可能为空）
  Future<Either<Failure, List<Explanation>>> getExplanationsByArtwork(
    String artworkName,
  );
}
