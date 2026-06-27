import 'dart:ui';

import 'package:firebase_analytics/firebase_analytics.dart';
import 'package:firebase_core/firebase_core.dart';
import 'package:firebase_crashlytics/firebase_crashlytics.dart';
import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_localizations/flutter_localizations.dart';
import 'theme/app_theme.dart';
import 'core/router/app_router.dart';
import 'core/theme/theme_mode_provider.dart';
import 'features/settings/presentation/providers/language_provider.dart';
import 'l10n/app_localizations.dart';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();

  // Firebase Crashlytics + Analytics（配置缺失时静默跳过，不影响应用启动）
  try {
    await Firebase.initializeApp();
    await FirebaseCrashlytics.instance
        .setCrashlyticsCollectionEnabled(!kDebugMode);
    FlutterError.onError = FirebaseCrashlytics.instance.recordFlutterFatalError;
    PlatformDispatcher.instance.onError = (error, stack) {
      FirebaseCrashlytics.instance.recordError(error, stack, fatal: true);
      return true;
    };
    await FirebaseAnalytics.instance.setAnalyticsCollectionEnabled(!kDebugMode);
  } catch (e) {
    debugPrint('Firebase init skipped: $e');
  }

  runApp(
    const ProviderScope(
      child: GoMuseumApp(),
    ),
  );
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

      // 国际化配置 —— UI 语言跟随设置页选择（languageProvider 持久化）
      locale: ref.watch(languageProvider),
      localizationsDelegates: const [
        AppLocalizations.delegate,
        GlobalMaterialLocalizations.delegate,
        GlobalWidgetsLocalizations.delegate,
        GlobalCupertinoLocalizations.delegate,
      ],
      supportedLocales: const [
        Locale('en'), // 英语
        Locale('zh'), // 中文
        Locale('fr'), // 法语
        Locale('de'), // 德语
        Locale('es'), // 西班牙语
        Locale('it'), // 意大利语
      ],

      // 调试配置
      debugShowCheckedModeBanner: false,
    );
  }
}
