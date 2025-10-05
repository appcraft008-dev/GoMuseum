import 'package:cross_file/cross_file.dart';
import 'package:crypto/crypto.dart';
import 'package:dartz/dartz.dart';
import '../../../../core/error/failures.dart';
import '../entities/recognition_result.dart';
import '../repositories/recognition_repository.dart';

/// UseCase业务逻辑
class RecognizeArtwork {
  final RecognitionRepository repository;

  const RecognizeArtwork({required this.repository});

  /// 执行识别
  Future<Either<Failure, RecognitionResult>> call(XFile imageFile) async {
    // 1. 验证图片
    final validationResult = await _validateImage(imageFile);
    if (validationResult != null) {
      return Left(validationResult);
    }

    // 2. 生成图片哈希(SHA256)
    final imageHash = await _generateImageHash(imageFile);

    // 3. 检查缓存
    final cachedResult = await repository.getCachedResult(imageHash);
    if (cachedResult.isRight()) {
      final cached = cachedResult.getOrElse(() => null);
      if (cached != null) {
        return Right(cached);
      }
    }

    // 4. 调用远程识别API
    return await repository.recognizeArtwork(imageFile);
  }

  /// 验证图片(格式/大小)
  Future<Failure?> _validateImage(XFile imageFile) async {
    try {
      // 读取文件字节（XFile 跨平台兼容）
      final bytes = await imageFile.readAsBytes();
      if (bytes.isEmpty) {
        return const ValidationFailure('Image file is empty');
      }

      // 检查文件大小(<10MB)
      if (bytes.length > 10 * 1024 * 1024) {
        return const ValidationFailure('Image size exceeds 10MB limit');
      }

      // 检查图片格式(JPEG/PNG)
      if (!_isValidImageFormat(bytes)) {
        return const ValidationFailure(
            'Unsupported image format. Only JPEG and PNG are supported');
      }

      return null;
    } catch (e) {
      return ValidationFailure('Failed to read image file: $e');
    }
  }

  /// 检查图片格式
  bool _isValidImageFormat(List<int> bytes) {
    if (bytes.length < 4) return false;

    // JPEG magic bytes: FF D8 FF
    if (bytes[0] == 0xFF && bytes[1] == 0xD8 && bytes[2] == 0xFF) {
      return true;
    }

    // PNG magic bytes: 89 50 4E 47
    if (bytes[0] == 0x89 &&
        bytes[1] == 0x50 &&
        bytes[2] == 0x4E &&
        bytes[3] == 0x47) {
      return true;
    }

    return false;
  }

  /// 生成图片哈希
  Future<String> _generateImageHash(XFile imageFile) async {
    final bytes = await imageFile.readAsBytes();
    final digest = sha256.convert(bytes);
    return digest.toString();
  }
}
