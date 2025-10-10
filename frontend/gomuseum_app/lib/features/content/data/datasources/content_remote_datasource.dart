import 'package:dio/dio.dart';
import 'package:gomuseum_app/core/error/exceptions.dart';
import 'package:gomuseum_app/features/content/data/models/explanation_model.dart';

/// 远程数据源接口
abstract class ContentRemoteDataSource {
  /// 生成艺术品讲解
  Future<ExplanationModel> generateExplanation({
    required String artworkName,
    required String artist,
    required String period,
    required String language,
    String? description,
  });

  /// 生成TTS音频
  /// 返回音频文件的URL
  Future<String> generateTtsAudio({
    required String text,
    required String language,
    String? voice,
    double? speed,
  });
}

/// 远程数据源实现
class ContentRemoteDataSourceImpl implements ContentRemoteDataSource {
  final Dio dio;

  const ContentRemoteDataSourceImpl({required this.dio});

  @override
  Future<ExplanationModel> generateExplanation({
    required String artworkName,
    required String artist,
    required String period,
    required String language,
    String? description,
  }) async {
    try {
      final requestData = {
        'artwork_name': artworkName,
        'artist': artist,
        'period': period,
        'language': language,
        if (description != null) 'description': description,
      };

      final response = await dio.post(
        '/api/v1/content/explanation',
        data: requestData,
        options: Options(
          headers: {
            'Accept': 'application/json',
            'Content-Type': 'application/json',
          },
          sendTimeout: const Duration(seconds: 30),
          receiveTimeout: const Duration(seconds: 30),
        ),
      );

      if (response.statusCode == 200) {
        return ExplanationModel.fromJson(response.data as Map<String, dynamic>);
      } else {
        throw ServerException(
            'Server returned status code: ${response.statusCode}');
      }
    } on DioException catch (e) {
      if (e.type == DioExceptionType.connectionTimeout ||
          e.type == DioExceptionType.receiveTimeout ||
          e.type == DioExceptionType.sendTimeout) {
        throw const TimeoutException('Request timeout after 30 seconds');
      } else if (e.type == DioExceptionType.connectionError) {
        throw const NetworkException('Network connection failed');
      } else {
        throw ServerException('Server error: ${e.message}');
      }
    } catch (e) {
      throw ServerException('Unexpected error: $e');
    }
  }

  @override
  Future<String> generateTtsAudio({
    required String text,
    required String language,
    String? voice,
    double? speed,
  }) async {
    try {
      final requestData = {
        'text': text,
        'language': language,
        if (voice != null) 'voice': voice,
        if (speed != null) 'speed': speed,
      };

      final response = await dio.post(
        '/api/v1/content/tts/generate',
        data: requestData,
        options: Options(
          headers: {
            'Accept': 'application/json',
            'Content-Type': 'application/json',
          },
          sendTimeout: const Duration(seconds: 60),
          receiveTimeout: const Duration(seconds: 60),
          // 接收二进制数据
          responseType: ResponseType.bytes,
        ),
      );

      if (response.statusCode == 200) {
        // 后端直接返回音频文件(MP3)
        // 这里返回一个临时URL或者Base64编码
        // 实际使用时需要保存到本地文件并返回路径
        // 暂时返回一个标识,实际实现需要在Repository层处理
        final audioData = response.data as List<int>;

        // 返回base64编码的音频数据URL scheme
        // 实际应用中应该保存到临时文件并返回文件路径
        return 'data:audio/mpeg;base64,${_base64Encode(audioData)}';
      } else {
        throw ServerException(
            'Server returned status code: ${response.statusCode}');
      }
    } on DioException catch (e) {
      if (e.type == DioExceptionType.connectionTimeout ||
          e.type == DioExceptionType.receiveTimeout ||
          e.type == DioExceptionType.sendTimeout) {
        throw const TimeoutException('Request timeout after 60 seconds');
      } else if (e.type == DioExceptionType.connectionError) {
        throw const NetworkException('Network connection failed');
      } else {
        throw ServerException('Server error: ${e.message}');
      }
    } catch (e) {
      throw ServerException('Unexpected error: $e');
    }
  }

  /// Base64编码辅助方法
  String _base64Encode(List<int> bytes) {
    const chars =
        'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/';
    final output = StringBuffer();

    for (var i = 0; i < bytes.length; i += 3) {
      final b1 = bytes[i];
      final b2 = i + 1 < bytes.length ? bytes[i + 1] : 0;
      final b3 = i + 2 < bytes.length ? bytes[i + 2] : 0;

      final n = (b1 << 16) | (b2 << 8) | b3;

      output.write(chars[(n >> 18) & 0x3F]);
      output.write(chars[(n >> 12) & 0x3F]);
      output.write(i + 1 < bytes.length ? chars[(n >> 6) & 0x3F] : '=');
      output.write(i + 2 < bytes.length ? chars[n & 0x3F] : '=');
    }

    return output.toString();
  }
}
