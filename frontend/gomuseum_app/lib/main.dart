import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_localizations/flutter_localizations.dart';
import 'theme/app_theme.dart';
import 'core/router/app_router.dart';

void main() {
  WidgetsFlutterBinding.ensureInitialized();

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
    return MaterialApp.router(
      title: 'GoMuseum',

      // 主题配置
      theme: AppTheme.lightTheme(),
      darkTheme: AppTheme.darkTheme(),
      themeMode: ThemeMode.system,

      // 路由配置
      routerConfig: goRouter,

      // 国际化配置
      localizationsDelegates: const [
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
