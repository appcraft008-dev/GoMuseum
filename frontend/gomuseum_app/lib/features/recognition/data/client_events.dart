import 'dart:convert';

import 'package:dio/dio.dart';
import 'package:gomuseum_app/core/error/exceptions.dart';
import 'package:shared_preferences/shared_preferences.dart';

/// 没发出去的最多攒几条(只留最新的)。
const kMaxPendingClientEvents = 20;
const _kPendingKey = 'pending_client_events';

/// App 侧埋点(V79)→ `POST /api/v1/recognize/client-event`:额度/语音付费墙真弹出来了、
/// 识别没拿到结果。没网时请求到不了后端,先攒在本机,下次任何一次上报前补发,
/// `at` 记真实发生时刻。吞掉一切异常:埋点绝不连累识别页。
Future<void> reportClientEvent(
  Dio dio,
  String name, {
  String? museum,
  String? qid,
  String? reason,
  String? deviceId,
}) async {
  try {
    final e = {
      'name': name,
      if (museum != null) 'museum': museum,
      if (qid != null) 'qid': qid,
      if (reason != null) 'reason': reason,
      if (deviceId != null) 'device_id': deviceId,
      'at': DateTime.now().millisecondsSinceEpoch / 1000,
    };
    final sp = await SharedPreferences.getInstance();
    final pending = <String>[
      ...(sp.getStringList(_kPendingKey) ?? []),
      jsonEncode(e),
    ];
    await sp.setStringList(_kPendingKey, pending);
    await flushClientEvents(dio);
  } catch (_) {}
}

/// 按顺序补发攒着的;遇到第一条发不出去就停(多半还是没网),剩下的留到下次。
Future<void> flushClientEvents(Dio dio) async {
  try {
    final sp = await SharedPreferences.getInstance();
    var pending = sp.getStringList(_kPendingKey) ?? [];
    if (pending.length > kMaxPendingClientEvents) {
      pending = pending.sublist(pending.length - kMaxPendingClientEvents);
    }
    while (pending.isNotEmpty) {
      try {
        await dio.post('/api/v1/recognize/client-event',
            data: jsonDecode(pending.first));
      } on DioException catch (e) {
        if (e.response == null) break; // 没网/断连:留着
        // 有响应却被拒(如 422):重发也没用,丢掉
      }
      pending = pending.sublist(1);
    }
    await sp.setStringList(_kPendingKey, pending);
  } catch (_) {}
}

/// 识别最终失败(重发也用完了)的原因,对应后端 `reason` 取值。
String recognitionFailureReason(Object e) => switch (e) {
      TimeoutException() => 'timeout',
      NetworkException(message: kGatewayUnavailable) => 'server',
      NetworkException() => 'no_network',
      ServerException() => 'server',
      _ => 'other',
    };
