import 'dart:async';
import 'dart:ui';

import 'package:firebase_analytics/firebase_analytics.dart';
import 'package:firebase_core/firebase_core.dart';
import 'package:firebase_crashlytics/firebase_crashlytics.dart';
import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_localizations/flutter_localizations.dart';
import 'theme/app_theme.dart';
import 'theme/gm_tokens.dart';
import 'core/router/app_router.dart';
import 'core/services/app_update_service.dart';
import 'core/services/media_session.dart';
import 'core/theme/theme_mode_provider.dart';
import 'features/settings/presentation/providers/language_provider.dart';
import 'l10n/app_localizations.dart';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();

  // Firebase Crashlytics + Analytics（配置缺失时静默跳过，不影响应用启动）
  try {
    await Firebase.initializeApp();
    await FirebaseCrashlytics.instance.setCrashlyticsCollectionEnabled(
      !kDebugMode,
    );
    // 界面层错误与异步错误(图片加载失败、字体下载断线等)不会让 App 退出,按非致命上报;
    // 真闪退由 Crashlytics 原生层抓
    FlutterError.onError = FirebaseCrashlytics.instance.recordFlutterError;
    PlatformDispatcher.instance.onError = (error, stack) {
      FirebaseCrashlytics.instance.recordError(error, stack, fatal: false);
      return true;
    };
    await FirebaseAnalytics.instance.setAnalyticsCollectionEnabled(!kDebugMode);
  } catch (e) {
    debugPrint('Firebase init skipped: $e');
  }

  // 系统播放卡片:不阻塞启动;没起来之前开播只是暂时没卡片
  unawaited(MediaSession.init());

  runApp(const ProviderScope(child: GoMuseumApp()));
  // 首帧后再查:Google 的更新小窗要盖在已渲染的界面上
  WidgetsBinding.instance.addPostFrameCallback((_) => checkForAppUpdate());
}

class GoMuseumApp extends ConsumerWidget {
  const GoMuseumApp({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final router = ref.watch(goRouterProvider);

    return MaterialApp.router(
      title: 'GoMuseum',

      // 主题配置
      theme: AppTheme.lightTheme(),
      darkTheme: AppTheme.darkTheme(),
      themeMode: ref.watch(themeModeProvider),

      // 路由配置 - 带认证守卫
      routerConfig: router,
      scaffoldMessengerKey: appMessengerKey,

      // 国际化配置 —— UI 语言跟随设置页选择（languageProvider 持久化）。
      // **null = 跟随系统**（未选过的用户的默认值）：Flutter 拿设备语言匹配
      // supportedLocales，匹配不上回退首项（en）。
      locale: ref.watch(languageProvider),
      localizationsDelegates: const [
        AppLocalizations.delegate,
        GlobalMaterialLocalizations.delegate,
        GlobalWidgetsLocalizations.delegate,
        GlobalCupertinoLocalizations.delegate,
      ],
      supportedLocales: kAppLocalesInResolutionOrder,
      // builder 在 Localizations 之内，换语言时先于页面重建 → GmText 的
      // 中日韩回退字体（JP/KR/TC/SC）跟着切。
      builder: (context, child) {
        GmText.locale = Localizations.localeOf(context);
        return child!;
      },

      // 调试配置
      debugShowCheckedModeBanner: false,
    );
  }
}
