/// GoMuseum 历史页面
library;

import 'package:flutter/material.dart';
import 'package:gomuseum_app/theme/dimensions.dart';
import 'package:gomuseum_app/ui/components/cards/history_card.dart';
import 'package:gomuseum_app/ui/components/feedback/empty_state_widget.dart';

class HistoryPage extends StatelessWidget {
  const HistoryPage({super.key});

  @override
  Widget build(BuildContext context) {
    final hasHistory = true; // TODO: 从状态管理获取

    return Scaffold(
      appBar: AppBar(
        title: const Text('识别历史'),
        actions: [
          IconButton(
            icon: const Icon(Icons.search),
            onPressed: () {},
          ),
        ],
      ),
      body: hasHistory
          ? ListView.builder(
              padding: EdgeInsets.symmetric(vertical: AppDimensions.spacing8),
              itemCount: 10,
              itemBuilder: (context, index) {
                return HistoryCard(
                  imageUrl: 'https://picsum.photos/200/200?random=$index',
                  title: '艺术品 ${index + 1}',
                  subtitle: '博物馆 ${index + 1}',
                  timestamp: DateTime.now().subtract(Duration(hours: index)),
                  onTap: () {},
                  onDelete: () {},
                );
              },
            )
          : const AppEmptyStateWidget(
              icon: Icons.history,
              title: '暂无历史记录',
              message: '开始识别艺术品，建立您的参观足迹',
            ),
    );
  }
}
