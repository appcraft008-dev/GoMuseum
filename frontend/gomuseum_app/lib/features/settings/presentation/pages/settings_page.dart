import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../../../l10n/app_localizations.dart';
import '../providers/language_provider.dart';

/// 设置页面
class SettingsPage extends ConsumerWidget {
  const SettingsPage({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final languageState = ref.watch(languageNotifierProvider);
    final l10n = AppLocalizations.of(context)!;

    return Scaffold(
      appBar: AppBar(
        title: Text(l10n.settings),
      ),
      body: ListView(
        children: [
          // 语言设置分组
          _buildSectionHeader(context, l10n.language),
          _buildLanguageSelector(context, ref, languageState),

          const Divider(height: 32),

          // 其他设置可以在这里添加
          _buildSectionHeader(context, l10n.about),
          ListTile(
            leading: const Icon(Icons.info_outline),
            title: Text(l10n.version),
            subtitle: const Text('0.1.0 (Step 2)'),
          ),
        ],
      ),
    );
  }

  Widget _buildSectionHeader(BuildContext context, String title) {
    return Padding(
      padding: const EdgeInsets.fromLTRB(16, 16, 16, 8),
      child: Text(
        title,
        style: Theme.of(context).textTheme.titleMedium?.copyWith(
              color: Theme.of(context).colorScheme.primary,
              fontWeight: FontWeight.bold,
            ),
      ),
    );
  }

  Widget _buildLanguageSelector(
    BuildContext context,
    WidgetRef ref,
    LanguageState languageState,
  ) {
    return Column(
      children: SupportedLanguage.values.map((language) {
        final isSelected = languageState.language == language;

        return ListTile(
          leading: Text(
            language.flag,
            style: const TextStyle(fontSize: 32),
          ),
          title: Text(language.name),
          subtitle: Text(language.code.toUpperCase()),
          trailing: isSelected
              ? Icon(
                  Icons.check_circle,
                  color: Theme.of(context).colorScheme.primary,
                )
              : null,
          selected: isSelected,
          onTap: () async {
            await ref
                .read(languageNotifierProvider.notifier)
                .setLanguage(language);

            if (context.mounted) {
              ScaffoldMessenger.of(context).showSnackBar(
                SnackBar(
                  content: Text('Language changed to ${language.name}'),
                  duration: const Duration(seconds: 2),
                ),
              );
            }
          },
        );
      }).toList(),
    );
  }
}
