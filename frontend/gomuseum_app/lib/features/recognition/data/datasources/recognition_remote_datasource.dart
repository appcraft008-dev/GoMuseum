import 'package:dio/dio.dart';
import 'package:gomuseum_app/core/error/exceptions.dart';
import 'package:gomuseum_app/features/recognition/data/models/recognition_result_model.dart';

/// 远程数据源接口
abstract class RecognitionRemoteDataSource {
  Future<RecognitionResultModel> recognizeArtwork(String base64Image);
}

/// 远程数据源实现
class RecognitionRemoteDataSourceImpl implements RecognitionRemoteDataSource {
  final Dio dio;

  const RecognitionRemoteDataSourceImpl({required this.dio});

  @override
  Future<RecognitionResultModel> recognizeArtwork(String base64Image) async {
    try {
      final response = await dio.post(
        '/api/v1/recognize',
        data: {'image': base64Image},
        options: Options(
          headers: {
            'Content-Type': 'application/json',
            'Accept': 'application/json',
          },
          sendTimeout: const Duration(seconds: 5),
          receiveTimeout: const Duration(seconds: 5),
        ),
      );

      if (response.statusCode == 200) {
        return RecognitionResultModel.fromJson(
            response.data as Map<String, dynamic>);
      } else {
        throw ServerException(
            'Server returned status code: ${response.statusCode}');
      }
    } on DioException catch (e) {
      if (e.type == DioExceptionType.connectionTimeout ||
          e.type == DioExceptionType.receiveTimeout ||
          e.type == DioExceptionType.sendTimeout) {
        throw const TimeoutException('Request timeout after 5 seconds');
      } else if (e.type == DioExceptionType.connectionError) {
        throw const NetworkException('Network connection failed');
      } else {
        throw ServerException('Server error: ${e.message}');
      }
    } catch (e) {
      throw ServerException('Unexpected error: $e');
    }
  }
}
