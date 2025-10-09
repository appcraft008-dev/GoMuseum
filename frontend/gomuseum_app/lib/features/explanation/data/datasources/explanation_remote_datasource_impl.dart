import 'package:dio/dio.dart';
import 'package:gomuseum_app/core/error/exceptions.dart';
import 'package:gomuseum_app/features/explanation/data/datasources/explanation_remote_datasource.dart';
import 'package:gomuseum_app/features/explanation/data/models/explanation_model.dart';
import 'package:logger/logger.dart';

/// 解释功能远程数据源实现
///
/// 使用Dio进行HTTP请求，负责与后端Explanation API交互。
/// 处理请求/响应的序列化、错误转换和日志记录。
class ExplanationRemoteDataSourceImpl implements ExplanationRemoteDataSource {
  final Dio dio;
  final Logger logger;

  /// API基础路径（相对于Dio baseUrl）
  static const String _baseApiPath = '/api/v1/explanation';

  const ExplanationRemoteDataSourceImpl({
    required this.dio,
    required this.logger,
  });

  @override
  Future<ExplanationModel> generateExplanation({
    required String artworkName,
    required String language,
    String detailLevel = 'standard',
    bool includeAudio = false,
    String? recognitionId,
  }) async {
    try {
      logger.i(
        'Generating explanation for artwork: $artworkName, '
        'language: $language, detailLevel: $detailLevel, '
        'includeAudio: $includeAudio',
      );

      // 构建请求体（snake_case）
      final requestBody = {
        'artwork_name': artworkName,
        'language': language,
        'detail_level': detailLevel,
        'include_audio': includeAudio,
        if (recognitionId != null) 'recognition_id': recognitionId,
      };

      final response = await dio.post(
        '$_baseApiPath/generate',
        data: requestBody,
        options: Options(
          headers: {
            'Accept': 'application/json',
            'Content-Type': 'application/json',
          },
          sendTimeout: const Duration(seconds: 30),
          receiveTimeout: const Duration(seconds: 30),
        ),
      );

      if (response.statusCode == 200 || response.statusCode == 201) {
        logger.d('Explanation generated successfully: ${response.data}');
        return ExplanationModel.fromJson(
          response.data as Map<String, dynamic>,
        );
      } else {
        throw ServerException(
          'Server returned status code: ${response.statusCode}',
        );
      }
    } on DioException catch (e) {
      logger.e('DioException in generateExplanation: ${e.type} - ${e.message}');
      _handleDioException(e);
    } catch (e) {
      logger.e('Unexpected error in generateExplanation: $e');
      throw ServerException('Unexpected error: $e');
    }
  }

  @override
  Future<ExplanationModel> getExplanationById(String id) async {
    try {
      logger.i('Fetching explanation by id: $id');

      final response = await dio.get(
        '$_baseApiPath/$id',
        options: Options(
          headers: {
            'Accept': 'application/json',
          },
          receiveTimeout: const Duration(seconds: 30),
        ),
      );

      if (response.statusCode == 200) {
        logger.d('Explanation fetched successfully: ${response.data}');
        return ExplanationModel.fromJson(
          response.data as Map<String, dynamic>,
        );
      } else {
        throw ServerException(
          'Server returned status code: ${response.statusCode}',
        );
      }
    } on DioException catch (e) {
      logger.e('DioException in getExplanationById: ${e.type} - ${e.message}');
      _handleDioException(e);
    } catch (e) {
      logger.e('Unexpected error in getExplanationById: $e');
      throw ServerException('Unexpected error: $e');
    }
  }

  @override
  Future<List<ExplanationModel>> getExplanationsByArtwork(
    String artworkName,
  ) async {
    try {
      logger.i('Fetching explanations for artwork: $artworkName');

      final response = await dio.get(
        _baseApiPath,
        queryParameters: {
          'artwork_name': artworkName,
        },
        options: Options(
          headers: {
            'Accept': 'application/json',
          },
          receiveTimeout: const Duration(seconds: 30),
        ),
      );

      if (response.statusCode == 200) {
        final List<dynamic> data = response.data as List<dynamic>;
        logger.d('Fetched ${data.length} explanations for $artworkName');

        return data
            .map((json) => ExplanationModel.fromJson(
                  json as Map<String, dynamic>,
                ))
            .toList();
      } else {
        throw ServerException(
          'Server returned status code: ${response.statusCode}',
        );
      }
    } on DioException catch (e) {
      logger.e(
        'DioException in getExplanationsByArtwork: ${e.type} - ${e.message}',
      );
      _handleDioException(e);
    } catch (e) {
      logger.e('Unexpected error in getExplanationsByArtwork: $e');
      throw ServerException('Unexpected error: $e');
    }
  }

  /// 处理Dio异常并转换为自定义异常
  ///
  /// 根据不同的异常类型抛出对应的自定义异常
  Never _handleDioException(DioException e) {
    // 超时异常
    if (e.type == DioExceptionType.connectionTimeout ||
        e.type == DioExceptionType.receiveTimeout ||
        e.type == DioExceptionType.sendTimeout) {
      throw const TimeoutException('Request timeout after 30 seconds');
    }

    // 网络连接异常
    if (e.type == DioExceptionType.connectionError) {
      throw const NetworkException('Network connection failed');
    }

    // HTTP响应异常
    if (e.response != null) {
      final statusCode = e.response!.statusCode;
      final responseData = e.response!.data;

      // 404 Not Found
      if (statusCode == 404) {
        throw NotFoundException(
          responseData is Map<String, dynamic> && responseData['detail'] != null
              ? responseData['detail'] as String
              : 'Resource not found',
        );
      }

      // 400 Bad Request (验证错误)
      if (statusCode == 400) {
        throw ValidationException(
          responseData is Map<String, dynamic> && responseData['detail'] != null
              ? responseData['detail'] as String
              : 'Validation failed',
        );
      }

      // 500 Server Error
      if (statusCode != null && statusCode >= 500) {
        throw ServerException(
          responseData is Map<String, dynamic> && responseData['detail'] != null
              ? responseData['detail'] as String
              : 'Server error occurred',
        );
      }
    }

    // 其他未知异常
    throw ServerException('Server error: ${e.message}');
  }
}
