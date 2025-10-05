import 'package:cross_file/cross_file.dart';
import 'package:dio/dio.dart';
import 'package:gomuseum_app/core/error/exceptions.dart';
import 'package:gomuseum_app/features/recognition/data/models/recognition_result_model.dart';
import 'package:http_parser/http_parser.dart';

/// 远程数据源接口
abstract class RecognitionRemoteDataSource {
  Future<RecognitionResultModel> recognizeArtwork(XFile imageFile);
}

/// 远程数据源实现
class RecognitionRemoteDataSourceImpl implements RecognitionRemoteDataSource {
  final Dio dio;

  const RecognitionRemoteDataSourceImpl({required this.dio});

  @override
  Future<RecognitionResultModel> recognizeArtwork(XFile imageFile) async {
    try {
      // 读取 XFile 字节数据（跨平台兼容）
      final bytes = await imageFile.readAsBytes();

      // 获取文件名
      final filename = imageFile.name;

      // 根据文件扩展名确定 MIME 类型
      final mimeType = _getMimeType(filename);

      // 使用 multipart/form-data 上传文件
      final formData = FormData.fromMap({
        'image': MultipartFile.fromBytes(
          bytes,
          filename: filename,
          contentType: MediaType.parse(mimeType),
        ),
      });

      final response = await dio.post(
        '/api/v1/recognition/recognize',
        data: formData,
        options: Options(
          headers: {
            'Accept': 'application/json',
          },
          sendTimeout: const Duration(seconds: 60),
          receiveTimeout: const Duration(seconds: 60),
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

  /// 根据文件名获取 MIME 类型
  String _getMimeType(String filename) {
    final ext = filename.toLowerCase().split('.').last;
    switch (ext) {
      case 'jpg':
      case 'jpeg':
        return 'image/jpeg';
      case 'png':
        return 'image/png';
      case 'gif':
        return 'image/gif';
      case 'webp':
        return 'image/webp';
      default:
        return 'image/jpeg'; // 默认为 JPEG
    }
  }
}
