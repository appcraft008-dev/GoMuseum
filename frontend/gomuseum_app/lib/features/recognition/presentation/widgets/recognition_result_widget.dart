import 'package:flutter/material.dart';
import 'package:intl/intl.dart';
import '../../../../l10n/app_localizations.dart';
import '../../domain/entities/recognition_result.dart';
import '../../../explanation/presentation/pages/explanation_page.dart';

/// 识别结果展示组件
class RecognitionResultWidget extends StatelessWidget {
  final RecognitionResult result;

  const RecognitionResultWidget({
    super.key,
    required this.result,
  });

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context)!;

    return SingleChildScrollView(
      child: Card(
        elevation: 4,
        child: Padding(
          padding: const EdgeInsets.all(16.0),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              // 标题
              Text(
                result.artworkName,
                style: Theme.of(context).textTheme.headlineSmall?.copyWith(
                      fontWeight: FontWeight.bold,
                    ),
              ),
              const SizedBox(height: 16),

              // 艺术家
              _buildInfoRow(
                context,
                icon: Icons.person,
                label: l10n.artist,
                value: result.artist,
              ),
              const SizedBox(height: 12),

              // 时期
              _buildInfoRow(
                context,
                icon: Icons.calendar_today,
                label: l10n.period,
                value: result.period,
              ),
              const SizedBox(height: 12),

              // 置信度
              _buildInfoRow(
                context,
                icon: Icons.analytics,
                label: l10n.confidence,
                value: '${(result.confidence * 100).toStringAsFixed(1)}%',
              ),
              const SizedBox(height: 12),

              // 识别时间
              _buildInfoRow(
                context,
                icon: Icons.access_time,
                label: l10n.recognizedAt,
                value: DateFormat('yyyy-MM-dd HH:mm').format(result.timestamp),
              ),
              const SizedBox(height: 16),

              // 描述
              const Divider(),
              const SizedBox(height: 8),
              Text(
                l10n.description,
                style: Theme.of(context).textTheme.titleMedium?.copyWith(
                      fontWeight: FontWeight.bold,
                    ),
              ),
              const SizedBox(height: 8),
              Text(
                result.description,
                style: Theme.of(context).textTheme.bodyMedium,
              ),
              const SizedBox(height: 24),

              // 获取详细解释按钮
              SizedBox(
                width: double.infinity,
                child: ElevatedButton.icon(
                  onPressed: () => _navigateToExplanation(context),
                  icon: const Icon(Icons.article),
                  label: Text(l10n.getDetailedExplanation),
                  style: ElevatedButton.styleFrom(
                    padding: const EdgeInsets.symmetric(vertical: 16),
                  ),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }

  void _navigateToExplanation(BuildContext context) {
    Navigator.push(
      context,
      MaterialPageRoute(
        builder: (context) => ExplanationPage(
          artworkName: result.artworkName,
          recognitionId: result.id,
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
        const SizedBox(width: 8),
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
