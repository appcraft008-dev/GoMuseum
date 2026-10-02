// 用系统浏览器打开网址;打不开就复制链接兜底。
//
// ⛔ 不用 `url_launcher`:它是原生插件、会改插件树,而 #434 那个致命缺陷
// 正长在插件树差异的缝里。这里走 MainActivity 里手写的通道(不是插件,
// 插件树不变),iOS 没接通道 → MissingPluginException → 落到复制兜底。
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:gomuseum_app/l10n/app_localizations.dart';

const _channel = MethodChannel('gomuseum/open_url');

Future<void> openUrlOrCopy(BuildContext context, String url) async {
  bool opened;
  try {
    opened = await _channel.invokeMethod<bool>('open', url) ?? false;
  } catch (_) {
    opened = false;
  }
  if (opened) return;
  // 没有浏览器 / 非 Android:至少把地址给到用户手里
  await Clipboard.setData(ClipboardData(text: url));
  if (!context.mounted) return;
  ScaffoldMessenger.of(context)
    ..clearSnackBars()
    ..showSnackBar(SnackBar(
      content: Text('${AppLocalizations.of(context)!.privacyLinkCopied}: $url'),
      duration: const Duration(seconds: 3),
      persist: false,
    ));
}
