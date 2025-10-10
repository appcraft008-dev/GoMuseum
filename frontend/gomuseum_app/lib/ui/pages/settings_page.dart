import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../l10n/app_localizations.dart';
import '../../features/settings/presentation/providers/language_provider.dart';

class SettingsPage extends ConsumerWidget {
  const SettingsPage({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l10n = AppLocalizations.of(context)!;
    final currentLocale = ref.watch(languageProvider);

    final languages = [
      ('en', 'English', '🇬🇧'),
      ('zh', '中文', '🇨🇳'),
      ('fr', 'Français', '🇫🇷'),
      ('de', 'Deutsch', '🇩🇪'),
      ('es', 'Español', '🇪🇸'),
      ('it', 'Italiano', '🇮🇹'),
    ];

    return Scaffold(
      appBar: AppBar(
        title: Text(l10n.settings),
      ),
      body: ListView(
        children: [
          ListTile(
            leading: const Icon(Icons.language),
            title: Text(l10n.language),
            subtitle: Text(l10n.selectLanguage),
          ),
          ...languages.map((lang) {
            final isSelected = currentLocale.languageCode == lang.$1;
            return ListTile(
              leading: Text(lang.$3, style: const TextStyle(fontSize: 24)),
              title: Text(lang.$2),
              trailing: isSelected
                  ? const Icon(Icons.check, color: Colors.blue)
                  : null,
              selected: isSelected,
              onTap: () {
                ref
                    .read(languageProvider.notifier)
                    .setLanguage(Locale(lang.$1));
              },
            );
          }),
        ],
      ),
    );
  }
}
