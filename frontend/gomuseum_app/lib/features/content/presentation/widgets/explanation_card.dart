import 'package:flutter/material.dart';
import 'package:gomuseum_app/features/content/domain/entities/explanation.dart';

/// 艺术品讲解卡片组件
class ExplanationCard extends StatelessWidget {
  final Explanation explanation;
  final VoidCallback? onTtsPlay;

  const ExplanationCard({
    super.key,
    required this.explanation,
    this.onTtsPlay,
  });

  @override
  Widget build(BuildContext context) {
    return Card(
      margin: const EdgeInsets.all(16),
      elevation: 2,
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // 标题
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                Expanded(
                  child: Text(
                    explanation.title,
                    style: Theme.of(context).textTheme.headlineSmall?.copyWith(
                          fontWeight: FontWeight.bold,
                        ),
                  ),
                ),
                if (onTtsPlay != null)
                  IconButton(
                    icon: const Icon(Icons.volume_up),
                    onPressed: onTtsPlay,
                    tooltip: 'Play Audio',
                  ),
              ],
            ),
            const SizedBox(height: 16),

            // 摘要
            _buildSection(
              context,
              title: 'Summary',
              content: explanation.summary,
            ),

            // 历史背景
            _buildSection(
              context,
              title: 'Historical Context',
              content: explanation.historicalContext,
            ),

            // 艺术分析
            _buildSection(
              context,
              title: 'Artistic Analysis',
              content: explanation.artisticAnalysis,
            ),

            // 文化意义
            _buildSection(
              context,
              title: 'Cultural Significance',
              content: explanation.culturalSignificance,
            ),

            // 有趣的事实
            if (explanation.interestingFacts.isNotEmpty)
              _buildFactsSection(context),
          ],
        ),
      ),
    );
  }

  Widget _buildSection(
    BuildContext context, {
    required String title,
    required String content,
  }) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          title,
          style: Theme.of(context).textTheme.titleMedium?.copyWith(
                fontWeight: FontWeight.bold,
                color: Theme.of(context).primaryColor,
              ),
        ),
        const SizedBox(height: 8),
        Text(
          content,
          style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                height: 1.5,
              ),
        ),
        const SizedBox(height: 16),
      ],
    );
  }

  Widget _buildFactsSection(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          'Interesting Facts',
          style: Theme.of(context).textTheme.titleMedium?.copyWith(
                fontWeight: FontWeight.bold,
                color: Theme.of(context).primaryColor,
              ),
        ),
        const SizedBox(height: 8),
        ...explanation.interestingFacts.asMap().entries.map((entry) {
          return Padding(
            padding: const EdgeInsets.only(bottom: 8),
            child: Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  '${entry.key + 1}. ',
                  style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                        fontWeight: FontWeight.bold,
                      ),
                ),
                Expanded(
                  child: Text(
                    entry.value,
                    style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                          height: 1.5,
                        ),
                  ),
                ),
              ],
            ),
          );
        }),
      ],
    );
  }
}
