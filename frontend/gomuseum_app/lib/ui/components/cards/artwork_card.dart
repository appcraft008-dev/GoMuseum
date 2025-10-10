/// GoMuseum 艺术品卡片组件
library;

import 'package:flutter/material.dart';
import 'package:gomuseum_app/theme/colors.dart';
import 'package:gomuseum_app/theme/dimensions.dart';

/// 艺术品卡片
class ArtworkCard extends StatelessWidget {
  final String imageUrl;
  final String title;
  final String artist;
  final double? confidence;
  final VoidCallback? onTap;
  final String? heroTag;

  const ArtworkCard({
    super.key,
    required this.imageUrl,
    required this.title,
    required this.artist,
    this.confidence,
    this.onTap,
    this.heroTag,
  });

  @override
  Widget build(BuildContext context) {
    final card = Card(
      clipBehavior: Clip.antiAlias,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(AppDimensions.radiusMedium),
      ),
      child: InkWell(
        onTap: onTap,
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // 图片
            AspectRatio(
              aspectRatio: 16 / 9,
              child: heroTag != null
                  ? Hero(
                      tag: heroTag!,
                      child: _buildImage(),
                    )
                  : _buildImage(),
            ),
            // 信息
            Padding(
              padding: EdgeInsets.all(AppDimensions.spacing12),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    title,
                    style: Theme.of(context).textTheme.titleMedium,
                    maxLines: 2,
                    overflow: TextOverflow.ellipsis,
                  ),
                  SizedBox(height: AppDimensions.spacing4),
                  Text(
                    artist,
                    style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                          color: AppColors.textSecondary,
                        ),
                  ),
                  if (confidence != null) ...[
                    SizedBox(height: AppDimensions.spacing8),
                    Row(
                      children: [
                        Expanded(
                          child: LinearProgressIndicator(
                            value: confidence,
                            backgroundColor: AppColors.primary.withValues(alpha: 0.2),
                            valueColor: AlwaysStoppedAnimation<Color>(AppColors.primary),
                          ),
                        ),
                        SizedBox(width: AppDimensions.spacing8),
                        Text(
                          '${(confidence! * 100).toStringAsFixed(0)}%',
                          style: Theme.of(context).textTheme.labelSmall,
                        ),
                      ],
                    ),
                  ],
                ],
              ),
            ),
          ],
        ),
      ),
    );

    return card;
  }

  Widget _buildImage() {
    return Image.network(
      imageUrl,
      fit: BoxFit.cover,
      errorBuilder: (context, error, stackTrace) {
        return Container(
          color: AppColors.primary.withValues(alpha: 0.1),
          child: Icon(
            Icons.image_not_supported,
            color: AppColors.textSecondary,
          ),
        );
      },
    );
  }
}
