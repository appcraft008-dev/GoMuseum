import 'package:flutter/material.dart';
import 'package:intl/intl.dart';

import '../../../../l10n/app_localizations.dart';
import '../../../../theme/tokens.dart';
import '../../../../ui/pages/explanation_page.dart';
import '../../domain/entities/recognition_result.dart';

/// 识别结果展示组件
class RecognitionResultWidget extends StatelessWidget {
  const RecognitionResultWidget({
    super.key,
    required this.result,
  });

  final RecognitionResult result;

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context)!;

    return SingleChildScrollView(
      child: Padding(
        padding: const EdgeInsets.only(bottom: GMSpace.s6),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Card(
              elevation: 4,
              child: Padding(
                padding: const EdgeInsets.all(GMSpace.s4),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    // 标题
                    Text(
                      result.artworkName,
                      style:
                          Theme.of(context).textTheme.headlineSmall?.copyWith(
                                fontWeight: FontWeight.bold,
                              ),
                    ),
                    const SizedBox(height: GMSpace.s3),

                    // 艺术家
                    _buildInfoRow(
                      context,
                      icon: Icons.person,
                      label: 'Artist',
                      value: result.artist,
                    ),
                    const SizedBox(height: GMSpace.s3),

                    // 时期
                    _buildInfoRow(
                      context,
                      icon: Icons.calendar_today,
                      label: 'Period',
                      value: result.period,
                    ),
                    const SizedBox(height: GMSpace.s3),

                    // 置信度
                    _buildInfoRow(
                      context,
                      icon: Icons.analytics,
                      label: 'Confidence',
                      value: '${(result.confidence * 100).toStringAsFixed(1)}%',
                    ),
                    const SizedBox(height: GMSpace.s3),

                    // 识别时间
                    _buildInfoRow(
                      context,
                      icon: Icons.access_time,
                      label: 'Recognized at',
                      value: DateFormat('yyyy-MM-dd HH:mm')
                          .format(result.timestamp),
                    ),
                    const SizedBox(height: GMSpace.s4),

                    // 描述
                    const Divider(),
                    const SizedBox(height: GMSpace.s2),
                    Text(
                      'Description',
                      style: Theme.of(context).textTheme.titleMedium?.copyWith(
                            fontWeight: FontWeight.bold,
                          ),
                    ),
                    const SizedBox(height: GMSpace.s2),
                    Text(
                      result.description,
                      style: Theme.of(context).textTheme.bodyMedium,
                    ),
                  ],
                ),
              ),
            ),
            const SizedBox(height: GMSpace.s4),
            FilledButton(
              onPressed: () {
                Navigator.push(
                  context,
                  MaterialPageRoute(
                    builder: (_) => ExplanationPage(
                      artworkId: result.id,
                      artworkName: result.artworkName,
                      description: result.description,
                    ),
                  ),
                );
              },
              style: FilledButton.styleFrom(
                backgroundColor: const Color(GMColors.brandAccent),
                foregroundColor: Colors.white,
                padding: const EdgeInsets.symmetric(vertical: GMSpace.s3),
              ),
              child: Text(l10n.viewExplanation),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildInfoRow(
    BuildContext context, {
    required IconData icon,
    required String label,
    required String value,
  }) {
    return Row(
      children: [
        Icon(icon, size: 20, color: Colors.grey[600]),
        const SizedBox(width: GMSpace.s2),
        Text(
          '$label: ',
          style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                fontWeight: FontWeight.w600,
                color: Colors.grey[700],
              ),
        ),
        Expanded(
          child: Text(
            value,
            style: Theme.of(context).textTheme.bodyMedium,
          ),
        ),
      ],
    );
  }
}
