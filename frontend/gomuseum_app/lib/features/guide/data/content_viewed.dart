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
    await dio.post(
      '/api/v1/museums/$slug/objects/$qid/viewed',
      data: {'from': entry.name},
    );
  } catch (_) {}
}

/// 收听结束为什么报(后端 `PlayedRequest.end`)。
enum ListenEnd { pause, complete, switch_, exit }

/// 完播率埋点 audio_played(V78)。同一次收听用同一个 [session]:暂停再续播会报多条,
/// 分析时按 session 取最大 [played]。吞掉一切异常。
Future<void> reportAudioPlayed(
  Dio dio, {
  required String slug,
  required String qid,
  required String language,
  required String section,
  int? qaSort,
  required Duration played,
  Duration? duration,
  required ListenEnd end,
  required String session,
}) async {
  try {
    await dio.post(
      '/api/v1/museums/$slug/objects/$qid/played',
      data: {
        'language': language,
        'section': section,
        'qa_sort': qaSort,
        'played_s': played.inMilliseconds / 1000,
        'duration_s': duration == null ? null : duration.inMilliseconds / 1000,
        'end': end == ListenEnd.switch_ ? 'switch' : end.name,
        'session': session,
      },
    );
  } catch (_) {}
}

/// 讲解 👍/👎 埋点 content_rated(V78)。吞掉一切异常。
Future<void> reportContentRated(
  Dio dio, {
  required String slug,
  required String qid,
  required String language,
  required bool up,
}) async {
  try {
    await dio.post(
      '/api/v1/museums/$slug/objects/$qid/rated',
      data: {'language': language, 'value': up ? 'up' : 'down'},
    );
  } catch (_) {}
}
