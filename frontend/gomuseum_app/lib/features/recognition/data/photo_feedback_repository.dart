import 'package:cross_file/cross_file.dart';
import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:http_parser/http_parser.dart';

import 'package:gomuseum_app/features/recognition/presentation/providers/recognition_providers.dart';
import 'package:gomuseum_app/features/settings/presentation/pages/settings_page.dart'
    show kVersionFootnote;

/// S5 识别照片反馈上传。**只在用户勾选后调用**;后台进行,失败重试一次后静默放弃 ——
/// 绝不打扰用户(他已经去看详情页了)。照 `feedback_repository.dart` 的轻量范式。
class PhotoFeedbackRepository {
  PhotoFeedbackRepository(this._dio,
      {this.retryDelay = const Duration(seconds: 3)});

  final Dio _dio;
  final Duration retryDelay;

  Future<void> send({
    required XFile image,
    required String trigger,
    required String phash,
    String? answerQid,
    String? museumSlug,
    String? language,
    String? queryText,
    String? labelText,
    String? text,
    String? deviceId,
  }) async {
    final bytes = await image.readAsBytes();
    FormData form() => FormData.fromMap({
          'image': MultipartFile.fromBytes(bytes,
              filename: 'photo.jpg', contentType: MediaType('image', 'jpeg')),
          'trigger': trigger,
          'phash': phash,
          if (answerQid != null) 'answer_qid': answerQid,
          if (museumSlug != null) 'museum_slug': museumSlug,
          if (language != null) 'language': language,
          if (queryText != null && queryText.trim().isNotEmpty)
            'query_text': queryText.trim(),
          if (labelText != null) 'label_text': labelText,
          if (text != null && text.trim().isNotEmpty) 'text': text.trim(),
          if (deviceId != null) 'device_id': deviceId,
          'app_version': kVersionFootnote,
        });
    for (var attempt = 0; attempt < 2; attempt++) {
      try {
        // FormData 只能发一次:每次重建
        await _dio.post('/api/v1/feedback/recognition-photo', data: form());
        return;
      } catch (_) {
        if (attempt == 0) await Future<void>.delayed(retryDelay);
      }
    }
  }
}

final photoFeedbackRepositoryProvider = Provider<PhotoFeedbackRepository>(
    (ref) => PhotoFeedbackRepository(ref.watch(dioProvider)));
