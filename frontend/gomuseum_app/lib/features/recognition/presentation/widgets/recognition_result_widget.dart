import 'package:flutter/material.dart';
import 'package:intl/intl.dart';
import '../../domain/entities/recognition_result.dart';

/// 识别结果展示组件
class RecognitionResultWidget extends StatelessWidget {
  final RecognitionResult result;

  const RecognitionResultWidget({
    super.key,
    required this.result,
  });

  @override
  Widget build(BuildContext context) {
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
                label: 'Artist',
                value: result.artist,
              ),
              const SizedBox(height: 12),

              // 时期
              _buildInfoRow(
                context,
                icon: Icons.calendar_today,
                label: 'Period',
                value: result.period,
              ),
              const SizedBox(height: 12),

              // 置信度
              _buildInfoRow(
                context,
                icon: Icons.analytics,
                label: 'Confidence',
                value: '${(result.confidence * 100).toStringAsFixed(1)}%',
              ),
              const SizedBox(height: 12),

              // 识别时间
              _buildInfoRow(
                context,
                icon: Icons.access_time,
                label: 'Recognized at',
                value: DateFormat('yyyy-MM-dd HH:mm').format(result.timestamp),
              ),
              const SizedBox(height: 16),

              // 描述
              const Divider(),
              const SizedBox(height: 8),
              Text(
                'Description',
                style: Theme.of(context).textTheme.titleMedium?.copyWith(
                      fontWeight: FontWeight.bold,
                    ),
              ),
              const SizedBox(height: 8),
              Text(
                result.description,
                style: Theme.of(context).textTheme.bodyMedium,
              ),
            ],
          ),
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
