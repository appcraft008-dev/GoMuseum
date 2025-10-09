import 'package:flutter/material.dart';

/// 语言选择器组件
///
/// 提供6种语言的选择界面（EN/FR/DE/ES/IT/ZH）。
/// 使用Material 3的SegmentedButton实现现代化UI。
class LanguageSelectorWidget extends StatelessWidget {
  /// 当前选中的语言代码
  final String selectedLanguage;

  /// 语言变更回调
  final ValueChanged<String> onLanguageChanged;

  /// 是否禁用交互（例如加载中）
  final bool enabled;

  const LanguageSelectorWidget({
    super.key,
    required this.selectedLanguage,
    required this.onLanguageChanged,
    this.enabled = true,
  });

  /// 支持的语言列表
  static const Map<String, String> supportedLanguages = {
    'en': 'English',
    'fr': 'Français',
    'de': 'Deutsch',
    'es': 'Español',
    'it': 'Italiano',
    'zh': '中文',
  };

  /// 获取语言的旗帜Emoji（可选装饰）
  static const Map<String, String> languageFlags = {
    'en': '🇬🇧',
    'fr': '🇫🇷',
    'de': '🇩🇪',
    'es': '🇪🇸',
    'it': '🇮🇹',
    'zh': '🇨🇳',
  };

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      mainAxisSize: MainAxisSize.min,
      children: [
        // 标题
        Padding(
          padding: const EdgeInsets.only(bottom: 12.0),
          child: Text(
            'Select Language',
            style: theme.textTheme.titleMedium?.copyWith(
              fontWeight: FontWeight.w600,
            ),
          ),
        ),

        // 语言选择按钮组
        SingleChildScrollView(
          scrollDirection: Axis.horizontal,
          child: SegmentedButton<String>(
            segments: supportedLanguages.entries.map((entry) {
              return ButtonSegment<String>(
                value: entry.key,
                label: Text(entry.value),
                icon: Text(languageFlags[entry.key] ?? ''),
              );
            }).toList(),
            selected: {selectedLanguage},
            onSelectionChanged: enabled
                ? (Set<String> selected) {
                    if (selected.isNotEmpty) {
                      onLanguageChanged(selected.first);
                    }
                  }
                : null,
            showSelectedIcon: true,
          ),
        ),

        // 选中语言提示
        if (enabled)
          Padding(
            padding: const EdgeInsets.only(top: 8.0),
            child: Text(
              'Currently selected: ${supportedLanguages[selectedLanguage]}',
              style: theme.textTheme.bodySmall?.copyWith(
                color: theme.colorScheme.onSurfaceVariant,
              ),
            ),
          ),
      ],
    );
  }
}

/// 紧凑版语言选择器（下拉菜单样式）
///
/// 适用于空间受限的场景，使用DropdownButton实现。
class CompactLanguageSelectorWidget extends StatelessWidget {
  /// 当前选中的语言代码
  final String selectedLanguage;

  /// 语言变更回调
  final ValueChanged<String> onLanguageChanged;

  /// 是否禁用交互
  final bool enabled;

  const CompactLanguageSelectorWidget({
    super.key,
    required this.selectedLanguage,
    required this.onLanguageChanged,
    this.enabled = true,
  });

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);

    return DropdownButton<String>(
      value: selectedLanguage,
      isExpanded: false,
      icon: const Icon(Icons.language),
      elevation: 16,
      style: theme.textTheme.bodyLarge,
      underline: Container(
        height: 2,
        color: theme.colorScheme.primary,
      ),
      onChanged: enabled
          ? (String? newValue) {
              if (newValue != null) {
                onLanguageChanged(newValue);
              }
            }
          : null,
      items: LanguageSelectorWidget.supportedLanguages.entries
          .map<DropdownMenuItem<String>>((entry) {
        return DropdownMenuItem<String>(
          value: entry.key,
          child: Row(
            mainAxisSize: MainAxisSize.min,
            children: [
              Text(
                LanguageSelectorWidget.languageFlags[entry.key] ?? '',
                style: const TextStyle(fontSize: 20),
              ),
              const SizedBox(width: 8),
              Text(entry.value),
            ],
          ),
        );
      }).toList(),
    );
  }
}
