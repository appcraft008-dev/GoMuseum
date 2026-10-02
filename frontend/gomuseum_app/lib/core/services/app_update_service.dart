// Play 应用内更新(后台下载流程):冷启动查一次 → 有新版就弹 Google 的小窗 →
// 用户同意后后台下载、照常用 App → 下完底部提示「重启」。
//
// 不强制、不纠缠:同一个新版本只问一次(拒了就等下一个版本)。
// 非 Play 安装 / iOS:通道失败或不存在 → 什么都不做。
// 原生侧是 MainActivity 手写通道(不加插件,理由同 open_url.dart)。
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:gomuseum_app/l10n/app_localizations.dart';
import 'package:shared_preferences/shared_preferences.dart';

const _channel = MethodChannel('gomuseum/app_update');
const kUpdatePromptedKey = 'app_update_prompted_version_code';

/// 全局 SnackBar 入口:「重启」提示不属于任何一页(下载完时用户可能在任何页面)。
final appMessengerKey = GlobalKey<ScaffoldMessengerState>();

bool shouldPromptUpdate({
  required bool available,
  required int versionCode,
  required int? lastPrompted,
}) =>
    available && (lastPrompted == null || versionCode > lastPrompted);

Future<void> checkForAppUpdate() async {
  _channel.setMethodCallHandler((call) async {
    if (call.method == 'downloaded') _showRestart();
  });
  Map<String, dynamic>? info;
  try {
    info = await _channel.invokeMapMethod<String, dynamic>('check');
  } catch (_) {
    return; // iOS / 测试环境没有这个通道
  }
  if (info == null) return;
  // 上次下完没重启(杀了进程),这次启动再提示一次
  if (info['downloaded'] == true) {
    _showRestart();
    return;
  }
  final vc = info['versionCode'] as int? ?? 0;
  final prefs = await SharedPreferences.getInstance();
  if (!shouldPromptUpdate(
    available: info['available'] == true,
    versionCode: vc,
    lastPrompted: prefs.getInt(kUpdatePromptedKey),
  )) {
    return;
  }
  // 先记再弹:用户点「以后」也算问过
  await prefs.setInt(kUpdatePromptedKey, vc);
  try {
    await _channel.invokeMethod<bool>('start');
  } catch (_) {}
}

void _showRestart() {
  final messenger = appMessengerKey.currentState;
  final ctx = appMessengerKey.currentContext;
  if (messenger == null || ctx == null) return;
  final l10n = AppLocalizations.of(ctx);
  if (l10n == null) return;
  // 带 action 的 SnackBar 默认常驻,直到点了或被别的提示顶掉;顶掉了下次冷启动会再提示
  messenger.showSnackBar(SnackBar(
    content: Text(l10n.updateReady),
    action: SnackBarAction(
      label: l10n.updateRestart,
      onPressed: () => _channel.invokeMethod('complete'),
    ),
  ));
}
