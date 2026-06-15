/// GoMuseum 识别结果页面
library;

import 'package:flutter/material.dart';
import 'package:gomuseum_app/theme/colors.dart';
import 'package:gomuseum_app/theme/dimensions.dart';
import 'package:gomuseum_app/ui/components/buttons/primary_button.dart';
import 'package:gomuseum_app/ui/components/buttons/icon_button_widget.dart';

class ResultPage extends StatelessWidget {
  final String artworkId;

  const ResultPage({super.key, required this.artworkId});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('识别结果'),
        actions: [
          AppIconButton(
            icon: Icons.favorite_border,
            onPressed: () {},
            tooltip: '收藏',
          ),
          AppIconButton(
            icon: Icons.share,
            onPressed: () {},
            tooltip: '分享',
          ),
        ],
      ),
      body: SingleChildScrollView(
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // 艺术品图片
            Hero(
              tag: 'artwork_$artworkId',
              child: AspectRatio(
                aspectRatio: 4 / 3,
                child: Image.network(
                  'https://picsum.photos/800/600',
                  fit: BoxFit.cover,
                ),
              ),
            ),

            // 信息卡片
            Padding(
              padding: EdgeInsets.all(AppDimensions.spacing16),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    '蒙娜丽莎',
                    style: Theme.of(context).textTheme.headlineMedium,
                  ),
                  SizedBox(height: AppDimensions.spacing8),
                  Text(
                    '列奥纳多·达·芬奇',
                    style: Theme.of(context).textTheme.titleMedium?.copyWith(
                          color: AppColors.textSecondary,
                        ),
                  ),
                  SizedBox(height: AppDimensions.spacing16),
                  Row(
                    children: [
                      Text(
                        '置信度:',
                        style: Theme.of(context).textTheme.bodyMedium,
                      ),
                      SizedBox(width: AppDimensions.spacing8),
                      Expanded(
                        child: LinearProgressIndicator(
                          value: 0.95,
                          backgroundColor:
                              AppColors.primary.withValues(alpha: 0.2),
                        ),
                      ),
                      SizedBox(width: AppDimensions.spacing8),
                      Text(
                        '95%',
                        style: Theme.of(context).textTheme.labelLarge,
                      ),
                    ],
                  ),
                ],
              ),
            ),

            const Divider(),

            // 讲解内容
            Padding(
              padding: EdgeInsets.all(AppDimensions.spacing16),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    mainAxisAlignment: MainAxisAlignment.spaceBetween,
                    children: [
                      Text(
                        '艺术品讲解',
                        style: Theme.of(context).textTheme.titleLarge,
                      ),
                      IconButton(
                        icon: const Icon(Icons.volume_up),
                        onPressed: null, // 禁用状态
                        tooltip: 'TTS功能即将推出',
                      ),
                    ],
                  ),
                  SizedBox(height: AppDimensions.spacing12),
                  Text(
                    '讲解功能即将推出...',
                    style: Theme.of(context).textTheme.bodyLarge?.copyWith(
                          color: AppColors.textSecondary,
                        ),
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}
