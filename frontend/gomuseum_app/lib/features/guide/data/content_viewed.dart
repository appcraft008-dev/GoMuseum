import 'package:dio/dio.dart';

/// 讲解页从哪进来(P3-14②)。名字与后端 `ViewedRequest.from` 一一对应。
enum GuideEntry { recognition, search, collection, history, home, link }

/// 进讲解页报一次 content_viewed。埋点挂了绝不连累页面:吞掉一切异常。
Future<void> reportContentViewed(
  Dio dio, {
  required String slug,
  required String qid,
  required GuideEntry entry,
}) async {
  try {
    await dio.post('/api/v1/museums/$slug/objects/$qid/viewed',
        data: {'from': entry.name});
  } catch (_) {}
}
