/// GoMuseum 反馈组件使用示例
///
/// 本文件展示了如何使用各种反馈组件
library;

import 'package:flutter/material.dart';
import 'loading_widget.dart';
import 'error_widget.dart';
import 'empty_state_widget.dart';

/// 反馈组件示例页面
class FeedbackWidgetsExample extends StatefulWidget {
  const FeedbackWidgetsExample({super.key});

  @override
  State<FeedbackWidgetsExample> createState() => _FeedbackWidgetsExampleState();
}

class _FeedbackWidgetsExampleState extends State<FeedbackWidgetsExample> {
  int _selectedIndex = 0;

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('反馈组件示例'),
      ),
      body: Column(
        children: [
          // 选项卡
          SingleChildScrollView(
            scrollDirection: Axis.horizontal,
            child: Row(
              children: [
                _buildTab('加载状态', 0),
                _buildTab('错误状态', 1),
                _buildTab('空状态', 2),
                _buildTab('骨架屏', 3),
              ],
            ),
          ),
          const Divider(height: 1),
          // 内容区域
          Expanded(
            child: _buildContent(),
          ),
        ],
      ),
    );
  }

  Widget _buildTab(String label, int index) {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 8.0),
      child: ChoiceChip(
        label: Text(label),
        selected: _selectedIndex == index,
        onSelected: (selected) {
          if (selected) {
            setState(() => _selectedIndex = index);
          }
        },
      ),
    );
  }

  Widget _buildContent() {
    switch (_selectedIndex) {
      case 0:
        return _buildLoadingExamples();
      case 1:
        return _buildErrorExamples();
      case 2:
        return _buildEmptyStateExamples();
      case 3:
        return _buildShimmerExamples();
      default:
        return const SizedBox();
    }
  }

  // ==================== 加载状态示例 ====================

  Widget _buildLoadingExamples() {
    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        _buildSection(
          '基础圆形加载',
          const AppLoadingWidget(),
        ),
        const SizedBox(height: 24),
        _buildSection(
          '带提示文字',
          const AppLoadingWidget.withText('加载中...'),
        ),
        const SizedBox(height: 24),
        _buildSection(
          '全屏加载遮罩',
          SizedBox(
            height: 200,
            child: Stack(
              children: [
                // 模拟背景内容
                Container(
                  color: Colors.grey[200],
                  child: const Center(
                    child: Text('背景内容'),
                  ),
                ),
                // 加载遮罩
                const AppLoadingWidget.fullScreen(
                  message: '正在识别艺术品...',
                ),
              ],
            ),
          ),
        ),
      ],
    );
  }

  // ==================== 错误状态示例 ====================

  Widget _buildErrorExamples() {
    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        _buildSection(
          '基础错误提示',
          AppErrorWidget(
            message: '加载失败',
            onRetry: () => _showSnackBar('重试中...'),
          ),
        ),
        const SizedBox(height: 24),
        _buildSection(
          '网络错误',
          AppErrorWidget.network(
            onRetry: () => _showSnackBar('重新连接中...'),
          ),
        ),
        const SizedBox(height: 24),
        _buildSection(
          '服务器错误',
          AppErrorWidget.server(
            onRetry: () => _showSnackBar('重新请求中...'),
          ),
        ),
        const SizedBox(height: 24),
        _buildSection(
          '内联错误提示',
          const InlineErrorWidget(
            message: '请输入有效的邮箱地址',
          ),
        ),
        const SizedBox(height: 24),
        _buildSection(
          '错误横幅',
          ErrorBanner(
            message: '同步失败，部分数据可能已过期',
            onDismiss: () => _showSnackBar('已关闭'),
            onAction: () => _showSnackBar('开始同步'),
            actionLabel: '立即同步',
          ),
        ),
      ],
    );
  }

  // ==================== 空状态示例 ====================

  Widget _buildEmptyStateExamples() {
    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        _buildSection(
          '基础空状态',
          const AppEmptyStateWidget(
            icon: Icons.inbox_outlined,
            title: '暂无内容',
            message: '这里还没有任何内容',
          ),
        ),
        const SizedBox(height: 24),
        _buildSection(
          '空历史记录',
          AppEmptyStateWidget.history(
            onAction: () => _showSnackBar('开始探索'),
          ),
        ),
        const SizedBox(height: 24),
        _buildSection(
          '空收藏',
          AppEmptyStateWidget.favorites(
            onAction: () => _showSnackBar('去发现'),
          ),
        ),
        const SizedBox(height: 24),
        _buildSection(
          '空搜索结果',
          AppEmptyStateWidget.searchResults(
            searchQuery: '莫奈',
            onAction: () => _showSnackBar('清除搜索'),
          ),
        ),
        const SizedBox(height: 24),
        _buildSection(
          '空列表占位',
          const EmptyListPlaceholder(
            message: '暂无数据',
          ),
        ),
      ],
    );
  }

  // ==================== 骨架屏示例 ====================

  Widget _buildShimmerExamples() {
    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        _buildSection(
          '矩形骨架屏',
          const ShimmerLoading(
            width: double.infinity,
            height: 200,
          ),
        ),
        const SizedBox(height: 24),
        _buildSection(
          '圆形骨架屏',
          const ShimmerLoading.circle(size: 80),
        ),
        const SizedBox(height: 24),
        _buildSection(
          '卡片骨架屏',
          const CardShimmer(),
        ),
        const SizedBox(height: 24),
        _buildSection(
          '列表项骨架屏',
          Column(
            children: const [
              ListItemShimmer(),
              ListItemShimmer(),
              ListItemShimmer(),
            ],
          ),
        ),
      ],
    );
  }

  // ==================== 辅助方法 ====================

  Widget _buildSection(String title, Widget child) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          title,
          style: Theme.of(context).textTheme.titleMedium?.copyWith(
                fontWeight: FontWeight.bold,
              ),
        ),
        const SizedBox(height: 12),
        Container(
          decoration: BoxDecoration(
            border: Border.all(color: Colors.grey[300]!),
            borderRadius: BorderRadius.circular(8),
          ),
          child: ClipRRect(
            borderRadius: BorderRadius.circular(8),
            child: child,
          ),
        ),
      ],
    );
  }

  void _showSnackBar(String message) {
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Text(message),
        duration: const Duration(seconds: 1),
      ),
    );
  }
}
