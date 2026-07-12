import 'package:cross_file/cross_file.dart';
import 'package:dio/dio.dart';
import 'package:gomuseum_app/core/error/exceptions.dart';
import 'package:gomuseum_app/features/recognition/data/models/recognition_result_model.dart';
import 'package:gomuseum_app/features/recognition/data/models/recognize_response.dart';
import 'package:http_parser/http_parser.dart';

/// 远程数据源接口
abstract class RecognitionRemoteDataSource {
  Future<RecognitionResultModel> recognizeArtwork(XFile imageFile);

  /// 接地识别端点。[slug] 为 null → 全局端点 `POST /recognize`（拍前不选馆）；
  /// 非 null → 老馆内端点 `POST /museums/{slug}/recognize`（兼容留路）。
  /// [mode] = `artwork`（默认）或 `label`（引导补拍墙签）。
  /// [deviceId] 非空时作为 `device_id` 查询参数发送——契约身份回退：
  /// 游客账号设备绑定，令牌抽风（multipart 刷新重试在 Dio 下不可靠，FormData 单次性）
  /// 时后端仍可凭 device_id 认出游客，识别不至于 401。
  Future<RecognizeResponse> recognize({
    String? slug,
    required XFile image,
    required String language,
    String mode,
    String? deviceId,
  });

  /// 确认卡点选「这一件」→ 上报「照片(phash)→qid」标注（喂后端 CLIP 校准）。
  /// fire-and-forget：吞掉所有异常，绝不打扰识别→讲解的跳转体验。
  Future<void> confirm({required String phash, required String qid});
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

  @override
  Future<RecognizeResponse> recognize({
    String? slug,
    required XFile image,
    required String language,
    String mode = 'artwork',
    String? deviceId,
  }) async {
    try {
      final bytes = await image.readAsBytes();
      final filename = image.name;
      final formData = FormData.fromMap({
        'image': MultipartFile.fromBytes(
          bytes,
          filename: filename,
          contentType: MediaType.parse(_getMimeType(filename)),
        ),
      });

      final url = slug == null
          ? '/api/v1/recognize'
          : '/api/v1/museums/$slug/recognize';
      final response = await dio.post(
        url,
        data: formData,
        queryParameters: {
          'language': language,
          'mode': mode,
          if (deviceId != null) 'device_id': deviceId,
        },
        options: Options(
          headers: {'Accept': 'application/json'},
          sendTimeout: const Duration(seconds: 60),
          receiveTimeout: const Duration(seconds: 60),
        ),
      );

      if (response.statusCode == 200) {
        return RecognizeResponse.fromJson(
            response.data as Map<String, dynamic>);
      }
      throw ServerException(
          'Server returned status code: ${response.statusCode}');
    } on DioException catch (e) {
      if (e.type == DioExceptionType.connectionTimeout ||
          e.type == DioExceptionType.receiveTimeout ||
          e.type == DioExceptionType.sendTimeout) {
        throw const TimeoutException('Request timeout after 60 seconds');
      } else if (e.type == DioExceptionType.connectionError) {
        throw const NetworkException('Network connection failed');
      }
      throw ServerException('Server error: ${e.message}');
    } catch (e) {
      if (e is ServerException || e is TimeoutException) rethrow;
      throw ServerException('Unexpected error: $e');
    }
  }

  @override
  Future<void> confirm({required String phash, required String qid}) async {
    try {
      await dio.post(
        '/api/v1/recognize/confirm',
        data: {'phash': phash, 'qid': qid},
        options: Options(headers: {'Accept': 'application/json'}),
      );
    } catch (_) {
      // fire-and-forget：任何失败都吞掉，绝不打扰 UX。
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
