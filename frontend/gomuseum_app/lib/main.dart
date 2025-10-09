import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_localizations/flutter_localizations.dart';
import 'l10n/app_localizations.dart';
import 'features/recognition/presentation/pages/recognition_page.dart';
import 'features/settings/presentation/pages/settings_page.dart';
import 'features/settings/presentation/providers/language_provider.dart';

void main() {
  runApp(const ProviderScope(child: GoMuseumApp()));
}

class GoMuseumApp extends ConsumerWidget {
  const GoMuseumApp({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final languageState = ref.watch(languageNotifierProvider);

    return MaterialApp(
      title: 'GoMuseum',
      theme: ThemeData(
        primarySwatch: Colors.blue,
        useMaterial3: true,
      ),
      locale: languageState.locale, // Use global language
      localizationsDelegates: const [
        AppLocalizations.delegate,
        GlobalMaterialLocalizations.delegate,
        GlobalWidgetsLocalizations.delegate,
        GlobalCupertinoLocalizations.delegate,
      ],
      supportedLocales: const [
        Locale('en'),
        Locale('zh'),
        Locale('fr'),
        Locale('de'),
        Locale('es'),
        Locale('it'),
      ],
      // 路由配置
      routes: {
        '/': (context) => const RecognitionPage(),
        '/settings': (context) => const SettingsPage(),
      },
      initialRoute: '/',
    );
  }
}
