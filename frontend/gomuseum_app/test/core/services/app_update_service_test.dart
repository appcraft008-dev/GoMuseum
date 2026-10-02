/// 应用内更新:同一个新版本只问一次;下载完提示重启;非 Play 安装什么都不做。
library;

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gomuseum_app/core/services/app_update_service.dart';
import 'package:gomuseum_app/l10n/app_localizations.dart';
import 'package:shared_preferences/shared_preferences.dart';

const _ch = MethodChannel('gomuseum/app_update');

/// [info] = 原生 check 的返回;记录 start/complete 调用。
List<String> _mockNative(WidgetTester t, Map<String, Object>? info) {
  final calls = <String>[];
  final m = t.binding.defaultBinaryMessenger;
  m.setMockMethodCallHandler(_ch, (call) async {
    calls.add(call.method);
    return call.method == 'check' ? info : null;
  });
  addTearDown(() => m.setMockMethodCallHandler(_ch, null));
  return calls;
}

Future<void> _pumpApp(WidgetTester t) => t.pumpWidget(MaterialApp(
      scaffoldMessengerKey: appMessengerKey,
      localizationsDelegates: AppLocalizations.localizationsDelegates,
      supportedLocales: AppLocalizations.supportedLocales,
      locale: const Locale('zh'),
      home: const Scaffold(),
    ));

void main() {
  test('只在有更新且这个版本没问过时才弹', () {
    expect(
        shouldPromptUpdate(
            available: true, versionCode: 48, lastPrompted: null),
        isTrue);
    expect(
        shouldPromptUpdate(available: true, versionCode: 48, lastPrompted: 48),
        isFalse,
        reason: '拒过的版本不再问');
    expect(
        shouldPromptUpdate(available: true, versionCode: 49, lastPrompted: 48),
        isTrue,
        reason: '出了更新的版本再问');
    expect(
        shouldPromptUpdate(
            available: false, versionCode: 49, lastPrompted: null),
        isFalse);
  });

  testWidgets('有新版:第一次启动弹,第二次启动(同版本)不再弹', (t) async {
    SharedPreferences.setMockInitialValues({});
    final calls = _mockNative(
        t, {'available': true, 'versionCode': 48, 'downloaded': false});
    await _pumpApp(t);
    await checkForAppUpdate();
    await checkForAppUpdate();
    expect(calls.where((c) => c == 'start').length, 1);
  });

  testWidgets('上次已下载没重启 → 提示重启,点了调 complete', (t) async {
    SharedPreferences.setMockInitialValues({});
    final calls = _mockNative(
        t, {'available': false, 'versionCode': 48, 'downloaded': true});
    await _pumpApp(t);
    await checkForAppUpdate();
    await t.pumpAndSettle(); // 等 SnackBar 滑入完再点
    expect(find.text('新版本已下载'), findsOneWidget);
    await t.tap(find.text('重启'));
    await t.pump();
    expect(calls, contains('complete'));
  });

  testWidgets('用着 App 时后台下完(原生推 downloaded)→ 提示重启', (t) async {
    SharedPreferences.setMockInitialValues({});
    _mockNative(
        t, {'available': false, 'versionCode': 48, 'downloaded': false});
    await _pumpApp(t);
    await checkForAppUpdate();
    await t.binding.defaultBinaryMessenger.handlePlatformMessage(
        _ch.name,
        const StandardMethodCodec()
            .encodeMethodCall(const MethodCall('downloaded')),
        (_) {});
    await t.pumpAndSettle();
    expect(find.text('新版本已下载'), findsOneWidget);
  });

  testWidgets('非 Play 安装(check 返回 null)/ 没有通道:什么都不做', (t) async {
    SharedPreferences.setMockInitialValues({});
    final calls = _mockNative(t, null);
    await _pumpApp(t);
    await checkForAppUpdate();
    expect(calls, ['check']);
    // iOS 没接通道 = MissingPluginException,不能冒出来
    t.binding.defaultBinaryMessenger.setMockMethodCallHandler(
        _ch, (_) async => throw MissingPluginException());
    await checkForAppUpdate();
    await t.pump();
    expect(find.byType(SnackBar), findsNothing);
  });
}
