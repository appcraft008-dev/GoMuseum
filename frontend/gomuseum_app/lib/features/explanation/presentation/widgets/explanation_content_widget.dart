import 'package:flutter/material.dart';
import 'package:intl/intl.dart';
import 'package:gomuseum_app/features/explanation/domain/entities/explanation.dart';
import 'package:gomuseum_app/features/explanation/presentation/widgets/language_selector_widget.dart';

/// 解释内容展示组件
///
/// 显示AI生成的艺术品解释内容，包括元数据和统计信息。
/// 使用Material 3设计规范，支持文本选择和复制。
class ExplanationContentWidget extends StatelessWidget {
  /// 解释实体数据
  final Explanation explanation;

  /// 是否显示完整元数据（可选）
  final bool showFullMetadata;

  /// 自定义内容样式（可选）
  final TextStyle? contentTextStyle;

  const ExplanationContentWidget({
    super.key,
    required this.explanation,
    this.showFullMetadata = true,
    this.contentTextStyle,
  });

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final dateFormat = DateFormat('yyyy-MM-dd HH:mm:ss');

    return SingleChildScrollView(
      padding: const EdgeInsets.all(16.0),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // 头部：作品名称
          _buildHeader(theme),

          const SizedBox(height: 16),

          // 元数据标签行
          _buildMetadataChips(theme),

          const SizedBox(height: 24),

          // 分割线
          const Divider(),

          const SizedBox(height: 24),

          // 解释内容（可选择文本）
          _buildContent(theme),

          const SizedBox(height: 24),

          // 详细元数据（可折叠）
          if (showFullMetadata) ...[
            const Divider(),
            const SizedBox(height: 16),
            _buildDetailedMetadata(theme, dateFormat),
          ],
        ],
      ),
    );
  }

  /// 构建头部：作品名称
  Widget _buildHeader(ThemeData theme) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          explanation.artworkName,
          style: theme.textTheme.headlineMedium?.copyWith(
            fontWeight: FontWeight.bold,
            color: theme.colorScheme.onSurface,
          ),
        ),
        const SizedBox(height: 4),
        Text(
          'Artwork Explanation',
          style: theme.textTheme.bodyMedium?.copyWith(
            color: theme.colorScheme.onSurfaceVariant,
          ),
        ),
      ],
    );
  }

  /// 构建元数据标签
  Widget _buildMetadataChips(ThemeData theme) {
    return Wrap(
      spacing: 8.0,
      runSpacing: 8.0,
      children: [
        // 语言标签
        Chip(
          avatar: Text(
            LanguageSelectorWidget.languageFlags[explanation.language] ?? '🌐',
            style: const TextStyle(fontSize: 16),
          ),
          label: Text(
            LanguageSelectorWidget.supportedLanguages[explanation.language] ??
                explanation.language.toUpperCase(),
          ),
          backgroundColor: theme.colorScheme.primaryContainer,
          labelStyle: TextStyle(
            color: theme.colorScheme.onPrimaryContainer,
            fontWeight: FontWeight.w500,
          ),
        ),

        // 详细级别标签
        Chip(
          avatar: Icon(
            _getDetailLevelIcon(explanation.metadata.detailLevel),
            size: 18,
            color: theme.colorScheme.onSecondaryContainer,
          ),
          label: Text(
            _formatDetailLevel(explanation.metadata.detailLevel),
          ),
          backgroundColor: theme.colorScheme.secondaryContainer,
          labelStyle: TextStyle(
            color: theme.colorScheme.onSecondaryContainer,
          ),
        ),

        // 字数统计标签
        Chip(
          avatar: Icon(
            Icons.text_fields,
            size: 18,
            color: theme.colorScheme.onTertiaryContainer,
          ),
          label: Text('${explanation.metadata.wordCount} words'),
          backgroundColor: theme.colorScheme.tertiaryContainer,
          labelStyle: TextStyle(
            color: theme.colorScheme.onTertiaryContainer,
          ),
        ),

        // 缓存状态标签
        if (explanation.cached)
          Chip(
            avatar: Icon(
              Icons.cached,
              size: 18,
              color: theme.colorScheme.onSurfaceVariant,
            ),
            label: const Text('Cached'),
            backgroundColor: theme.colorScheme.surfaceContainerHighest,
          ),
      ],
    );
  }

  /// 构建解释内容
  Widget _buildContent(ThemeData theme) {
    return Container(
      padding: const EdgeInsets.all(16.0),
      decoration: BoxDecoration(
        color: theme.colorScheme.surfaceContainerLow,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(
          color: theme.colorScheme.outlineVariant,
          width: 1,
        ),
      ),
      child: SelectableText(
        explanation.content,
        style: contentTextStyle ??
            theme.textTheme.bodyLarge?.copyWith(
              height: 1.6,
              letterSpacing: 0.15,
              color: theme.colorScheme.onSurface,
            ),
        textAlign: TextAlign.justify,
      ),
    );
  }

  /// 构建详细元数据
  Widget _buildDetailedMetadata(ThemeData theme, DateFormat dateFormat) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          'Metadata',
          style: theme.textTheme.titleSmall?.copyWith(
            fontWeight: FontWeight.w600,
            color: theme.colorScheme.onSurfaceVariant,
          ),
        ),
        const SizedBox(height: 12),
        _buildMetadataRow(
          theme,
          icon: Icons.access_time,
          label: 'Generated',
          value: dateFormat.format(explanation.timestamp),
        ),
        _buildMetadataRow(
          theme,
          icon: Icons.timer,
          label: 'Processing Time',
          value: '${explanation.processingTimeMs} ms',
        ),
        _buildMetadataRow(
          theme,
          icon: Icons.fingerprint,
          label: 'ID',
          value: explanation.id,
        ),
        if (explanation.audioUrl != null)
          _buildMetadataRow(
            theme,
            icon: Icons.audiotrack,
            label: 'Audio Available',
            value: explanation.audioDurationSeconds != null
                ? '${explanation.audioDurationSeconds} seconds'
                : 'Yes',
          ),
      ],
    );
  }

  /// 构建元数据行
  Widget _buildMetadataRow(
    ThemeData theme, {
    required IconData icon,
    required String label,
    required String value,
  }) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 6.0),
      child: Row(
        children: [
          Icon(
            icon,
            size: 16,
            color: theme.colorScheme.onSurfaceVariant,
          ),
          const SizedBox(width: 8),
          Text(
            '$label: ',
            style: theme.textTheme.bodySmall?.copyWith(
              fontWeight: FontWeight.w500,
              color: theme.colorScheme.onSurfaceVariant,
            ),
          ),
          Expanded(
            child: Text(
              value,
              style: theme.textTheme.bodySmall?.copyWith(
                color: theme.colorScheme.onSurface,
              ),
              overflow: TextOverflow.ellipsis,
            ),
          ),
        ],
      ),
    );
  }

  /// 获取详细级别对应的图标
  IconData _getDetailLevelIcon(String detailLevel) {
    switch (detailLevel) {
      case 'brief':
        return Icons.short_text;
      case 'detailed':
        return Icons.article;
      case 'standard':
      default:
        return Icons.notes;
    }
  }

  /// 格式化详细级别文本
  String _formatDetailLevel(String detailLevel) {
    return detailLevel[0].toUpperCase() + detailLevel.substring(1);
  }
}
