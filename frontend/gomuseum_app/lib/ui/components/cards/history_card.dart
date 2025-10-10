/// GoMuseum 历史记录卡片组件
library;

import 'package:flutter/material.dart';
import 'package:gomuseum_app/theme/colors.dart';
import 'package:gomuseum_app/theme/dimensions.dart';

/// 历史记录卡片
class HistoryCard extends StatelessWidget {
  final String imageUrl;
  final String title;
  final String subtitle;
  final DateTime timestamp;
  final VoidCallback? onTap;
  final VoidCallback? onDelete;

  const HistoryCard({
    super.key,
    required this.imageUrl,
    required this.title,
    required this.subtitle,
    required this.timestamp,
    this.onTap,
    this.onDelete,
  });

  @override
  Widget build(BuildContext context) {
    final card = Card(
      margin: EdgeInsets.symmetric(
        horizontal: AppDimensions.spacing16,
        vertical: AppDimensions.spacing8,
      ),
      child: InkWell(
        onTap: onTap,
        child: Padding(
          padding: EdgeInsets.all(AppDimensions.spacing12),
          child: Row(
            children: [
              // 缩略图
              ClipRRect(
                borderRadius: BorderRadius.circular(AppDimensions.radiusSmall),
                child: Image.network(
                  imageUrl,
                  width: 60,
                  height: 60,
                  fit: BoxFit.cover,
                  errorBuilder: (context, error, stackTrace) {
                    return Container(
                      width: 60,
                      height: 60,
                      color: AppColors.primary.withValues(alpha: 0.1),
                      child: Icon(Icons.image, color: AppColors.textSecondary),
                    );
                  },
                ),
              ),
              SizedBox(width: AppDimensions.spacing12),
              // 信息
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      title,
                      style: Theme.of(context).textTheme.titleSmall,
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                    ),
                    SizedBox(height: AppDimensions.spacing4),
                    Text(
                      subtitle,
                      style: Theme.of(context).textTheme.bodySmall?.copyWith(
                            color: AppColors.textSecondary,
                          ),
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                    ),
                    SizedBox(height: AppDimensions.spacing4),
                    Text(
                      _formatTime(timestamp),
                      style: Theme.of(context).textTheme.labelSmall?.copyWith(
                            color: AppColors.textSecondary,
                          ),
                    ),
                  ],
                ),
              ),
            ],
          ),
        ),
      ),
    );

    if (onDelete != null) {
      return Dismissible(
        key: ValueKey(timestamp.toString()),
        direction: DismissDirection.endToStart,
        onDismissed: (_) => onDelete?.call(),
        background: Container(
          color: AppColors.error,
          alignment: Alignment.centerRight,
          padding: EdgeInsets.only(right: AppDimensions.spacing16),
          child: const Icon(Icons.delete, color: Colors.white),
        ),
        child: card,
      );
    }

    return card;
  }

  String _formatTime(DateTime time) {
    final now = DateTime.now();
    final diff = now.difference(time);

    if (diff.inDays > 0) {
      return '${diff.inDays}天前';
    } else if (diff.inHours > 0) {
      return '${diff.inHours}小时前';
    } else if (diff.inMinutes > 0) {
      return '${diff.inMinutes}分钟前';
    } else {
      return '刚刚';
    }
  }
}
