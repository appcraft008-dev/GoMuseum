import 'dart:io' show Platform;

import 'package:dio/dio.dart';

import 'package:gomuseum_app/features/settings/presentation/pages/settings_page.dart'
    show kVersionFootnote;

/// 反馈上报。照 `auth_repository.dart` 的轻量范式写：一个 POST、没有 domain 逻辑，
/// 不建 datasource/entity/usecase 三层（那是为复杂领域准备的）。
class FeedbackRepository {
  FeedbackRepository(this._dio);

  final Dio _dio;

  /// 提交一条反馈。成功 true，失败 false（**不抛**：调用方要据此保留用户填的文本）。
  ///
  /// [language] 必须是**API 语言参数**（繁体是 `zh-hant` 不是 `zh`），不是 UI locale。
  /// 10 语是 10 份独立内容，带错语种 = 让人去修错的那一行。
  Future<bool> submit({
    required String scope,
    required String kind,
    String? museumSlug,
    String? qid,
    String? language,
    String? text,
    String? deviceId,
  }) async {
    try {
      final r = await _dio.post<void>(
        '/api/v1/feedback',
        data: {
          'scope': scope,
          'kind': kind,
          if (museumSlug != null) 'museum_slug': museumSlug,
          if (qid != null) 'qid': qid,
          if (language != null) 'language': language,
          if (text != null && text.trim().isNotEmpty) 'text': text.trim(),
          if (deviceId != null) 'device_id': deviceId,
          // 手工维护的常量（package_info_plus 是原生插件，被禁）。忘了改会被
          // settings_version_test 拦下，所以整串直接送，不做字符串处理。
          'app_version': kVersionFootnote,
          'platform': Platform.isIOS ? 'ios' : 'android',
        },
      );
      return r.statusCode == 204 || r.statusCode == 200;
    } on DioException {
      return false;
    }
  }
}
