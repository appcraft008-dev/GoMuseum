/// 讲解页「分享」:下载服务端合成的分享图 → 系统分享面板发「图 + 文字 + 链接」。
///
/// 图下载失败就只发文字 + 链接:分享这个动作不该因为一张图失败。
/// 微信会丢掉附带文字只收图 —— 已知且接受(spec §六)。
library;

import 'dart:typed_data';

import 'package:dio/dio.dart';
import 'package:gomuseum_app/features/content/data/models/object_content_model.dart';
import 'package:share_plus/share_plus.dart';

Future<Uint8List?> _download(String url) async {
  if (url.isEmpty) return null;
  try {
    final r = await Dio(BaseOptions(receiveTimeout: const Duration(seconds: 8)))
        .get<List<int>>(url,
            options: Options(responseType: ResponseType.bytes));
    final data = r.data;
    return data == null ? null : Uint8List.fromList(data);
  } catch (_) {
    return null;
  }
}

Future<void> _send(ShareParams p) async {
  await SharePlus.instance.share(p);
}

Future<void> shareObject(
  ShareInfo s, {
  Future<Uint8List?> Function(String url)? fetch,
  Future<void> Function(ShareParams p)? send,
}) async {
  final text = s.text.isEmpty ? s.url : '${s.text}\n${s.url}';
  final bytes = await (fetch ?? _download)(s.imageUrl);
  await (send ?? _send)(ShareParams(
    text: text,
    files: bytes == null
        ? null
        : [XFile.fromData(bytes, mimeType: 'image/jpeg', name: 'gomuseum.jpg')],
  ));
}
