/// GoMuseum 按钮组件展示页
///
/// 演示所有按钮组件的各种用法和变体
library;

import 'package:flutter/material.dart';
import 'package:gomuseum_app/theme/colors.dart';
import 'package:gomuseum_app/theme/dimensions.dart';
import 'package:gomuseum_app/ui/components/buttons/buttons.dart';

/// 按钮展示页面
class ButtonsShowcase extends StatefulWidget {
  const ButtonsShowcase({super.key});

  @override
  State<ButtonsShowcase> createState() => _ButtonsShowcaseState();
}

class _ButtonsShowcaseState extends State<ButtonsShowcase> {
  bool isLoading = false;

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('按钮组件展示'),
        backgroundColor: AppColors.primary,
        foregroundColor: Colors.white,
      ),
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(AppDimensions.spacing16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // ==================== PrimaryButton 示例 ====================
            _buildSectionTitle('主要按钮 (PrimaryButton)'),
            const SizedBox(height: AppDimensions.spacing12),

            // 基础用法
            PrimaryButton(
              text: '基础按钮',
              onPressed: () => _showSnackBar('基础按钮被点击'),
            ),
            const SizedBox(height: AppDimensions.spacing12),

            // 带图标
            PrimaryButton(
              text: '上传照片',
              icon: Icons.upload,
              onPressed: () => _showSnackBar('上传照片'),
            ),
            const SizedBox(height: AppDimensions.spacing12),

            // 加载状态
            PrimaryButton(
              text: '处理中...',
              isLoading: isLoading,
              onPressed: () => _toggleLoading(),
            ),
            const SizedBox(height: AppDimensions.spacing12),

            // 全宽按钮
            PrimaryButton(
              text: '全宽按钮',
              isFullWidth: true,
              onPressed: () => _showSnackBar('全宽按钮被点击'),
            ),
            const SizedBox(height: AppDimensions.spacing12),

            // 禁用状态
            const PrimaryButton(
              text: '禁用按钮',
              onPressed: null,
            ),
            const SizedBox(height: AppDimensions.spacing12),

            // 自定义尺寸
            Row(
              children: [
                PrimaryButton(
                  text: '小',
                  width: 80,
                  height: AppDimensions.buttonHeightSmall,
                  onPressed: () => _showSnackBar('小按钮'),
                ),
                const SizedBox(width: AppDimensions.spacing8),
                PrimaryButton(
                  text: '中',
                  width: 100,
                  onPressed: () => _showSnackBar('中按钮'),
                ),
                const SizedBox(width: AppDimensions.spacing8),
                Expanded(
                  child: PrimaryButton(
                    text: '大',
                    onPressed: () => _showSnackBar('大按钮'),
                  ),
                ),
              ],
            ),

            const SizedBox(height: AppDimensions.spacing32),

            // ==================== SecondaryButton 示例 ====================
            _buildSectionTitle('次要按钮 (SecondaryButton)'),
            const SizedBox(height: AppDimensions.spacing12),

            // 基础用法
            SecondaryButton(
              text: '取消',
              onPressed: () => _showSnackBar('取消按钮被点击'),
            ),
            const SizedBox(height: AppDimensions.spacing12),

            // 带图标
            SecondaryButton(
              text: '查看详情',
              icon: Icons.info_outline,
              onPressed: () => _showSnackBar('查看详情'),
            ),
            const SizedBox(height: AppDimensions.spacing12),

            // 全宽按钮
            SecondaryButton(
              text: '稍后再说',
              isFullWidth: true,
              onPressed: () => _showSnackBar('稍后再说'),
            ),
            const SizedBox(height: AppDimensions.spacing12),

            // 禁用状态
            const SecondaryButton(
              text: '不可用',
              onPressed: null,
            ),
            const SizedBox(height: AppDimensions.spacing12),

            // 自定义颜色 - 危险操作
            SecondaryButton(
              text: '删除',
              icon: Icons.delete_outline,
              borderColor: AppColors.error,
              textColor: AppColors.error,
              onPressed: () => _showSnackBar('删除操作'),
            ),
            const SizedBox(height: AppDimensions.spacing12),

            // 主要和次要按钮组合
            Row(
              children: [
                Expanded(
                  child: SecondaryButton(
                    text: '取消',
                    onPressed: () => _showSnackBar('取消'),
                  ),
                ),
                const SizedBox(width: AppDimensions.spacing12),
                Expanded(
                  child: PrimaryButton(
                    text: '确认',
                    onPressed: () => _showSnackBar('确认'),
                  ),
                ),
              ],
            ),

            const SizedBox(height: AppDimensions.spacing32),

            // ==================== IconButtonWidget 示例 ====================
            _buildSectionTitle('图标按钮 (IconButtonWidget)'),
            const SizedBox(height: AppDimensions.spacing12),

            // 基础图标按钮
            Wrap(
              spacing: AppDimensions.spacing12,
              runSpacing: AppDimensions.spacing12,
              children: [
                IconButtonWidget(
                  icon: Icons.favorite_border,
                  tooltip: '收藏',
                  onPressed: () => _showSnackBar('收藏'),
                ),
                IconButtonWidget(
                  icon: Icons.share,
                  tooltip: '分享',
                  onPressed: () => _showSnackBar('分享'),
                ),
                IconButtonWidget(
                  icon: Icons.edit,
                  tooltip: '编辑',
                  onPressed: () => _showSnackBar('编辑'),
                ),
                const IconButtonWidget(
                  icon: Icons.delete,
                  tooltip: '删除 (禁用)',
                  onPressed: null,
                ),
              ],
            ),

            const SizedBox(height: AppDimensions.spacing16),

            // 带背景的图标按钮
            Wrap(
              spacing: AppDimensions.spacing12,
              runSpacing: AppDimensions.spacing12,
              children: [
                IconButtonWidget(
                  icon: Icons.favorite,
                  tooltip: '主色背景',
                  hasBackground: true,
                  variant: IconButtonVariant.primary,
                  onPressed: () => _showSnackBar('主色图标'),
                ),
                IconButtonWidget(
                  icon: Icons.star,
                  tooltip: '辅色背景',
                  hasBackground: true,
                  variant: IconButtonVariant.secondary,
                  onPressed: () => _showSnackBar('辅色图标'),
                ),
                IconButtonWidget(
                  icon: Icons.check_circle,
                  tooltip: '成功',
                  hasBackground: true,
                  variant: IconButtonVariant.success,
                  onPressed: () => _showSnackBar('成功'),
                ),
                IconButtonWidget(
                  icon: Icons.error,
                  tooltip: '错误',
                  hasBackground: true,
                  variant: IconButtonVariant.danger,
                  onPressed: () => _showSnackBar('错误'),
                ),
                IconButtonWidget(
                  icon: Icons.warning,
                  tooltip: '警告',
                  hasBackground: true,
                  variant: IconButtonVariant.warning,
                  onPressed: () => _showSnackBar('警告'),
                ),
                IconButtonWidget(
                  icon: Icons.info,
                  tooltip: '信息',
                  hasBackground: true,
                  variant: IconButtonVariant.info,
                  onPressed: () => _showSnackBar('信息'),
                ),
              ],
            ),

            const SizedBox(height: AppDimensions.spacing16),

            // 不同尺寸的图标按钮
            Wrap(
              spacing: AppDimensions.spacing12,
              runSpacing: AppDimensions.spacing12,
              crossAxisAlignment: WrapCrossAlignment.center,
              children: [
                IconButtonWidget(
                  icon: Icons.settings,
                  tooltip: '小',
                  size: 32,
                  iconSize: 16,
                  hasBackground: true,
                  variant: IconButtonVariant.primary,
                  onPressed: () => _showSnackBar('小图标'),
                ),
                IconButtonWidget(
                  icon: Icons.settings,
                  tooltip: '中',
                  size: 40,
                  iconSize: 20,
                  hasBackground: true,
                  variant: IconButtonVariant.primary,
                  onPressed: () => _showSnackBar('中图标'),
                ),
                IconButtonWidget(
                  icon: Icons.settings,
                  tooltip: '大',
                  size: 48,
                  iconSize: 24,
                  hasBackground: true,
                  variant: IconButtonVariant.primary,
                  onPressed: () => _showSnackBar('大图标'),
                ),
                IconButtonWidget(
                  icon: Icons.settings,
                  tooltip: '超大',
                  size: 56,
                  iconSize: 28,
                  hasBackground: true,
                  variant: IconButtonVariant.primary,
                  onPressed: () => _showSnackBar('超大图标'),
                ),
              ],
            ),

            const SizedBox(height: AppDimensions.spacing32),

            // ==================== 综合示例 ====================
            _buildSectionTitle('综合示例 - 艺术品卡片'),
            const SizedBox(height: AppDimensions.spacing12),

            _buildArtworkCard(),

            const SizedBox(height: AppDimensions.spacing32),
          ],
        ),
      ),
    );
  }

  Widget _buildSectionTitle(String title) {
    return Text(
      title,
      style: const TextStyle(
        fontSize: 18,
        fontWeight: FontWeight.bold,
        color: AppColors.textPrimaryLight,
      ),
    );
  }

  Widget _buildArtworkCard() {
    return Container(
      padding: const EdgeInsets.all(AppDimensions.spacing16),
      decoration: BoxDecoration(
        color: AppColors.cardLight,
        borderRadius: BorderRadius.circular(AppDimensions.radiusMedium),
        border: Border.all(color: AppColors.borderLight),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              const Expanded(
                child: Text(
                  '蒙娜丽莎',
                  style: TextStyle(
                    fontSize: 18,
                    fontWeight: FontWeight.bold,
                    color: AppColors.textPrimaryLight,
                  ),
                ),
              ),
              IconButtonWidget(
                icon: Icons.favorite_border,
                tooltip: '收藏',
                onPressed: () => _showSnackBar('收藏艺术品'),
              ),
              const SizedBox(width: AppDimensions.spacing8),
              IconButtonWidget(
                icon: Icons.share,
                tooltip: '分享',
                onPressed: () => _showSnackBar('分享艺术品'),
              ),
            ],
          ),
          const SizedBox(height: AppDimensions.spacing8),
          const Text(
            '列奥纳多·达·芬奇',
            style: TextStyle(
              fontSize: 14,
              color: AppColors.textSecondaryLight,
              fontStyle: FontStyle.italic,
            ),
          ),
          const SizedBox(height: AppDimensions.spacing16),
          const Text(
            '创作于1503-1519年间，是世界上最著名的画作之一。',
            style: TextStyle(
              fontSize: 14,
              color: AppColors.textPrimaryLight,
            ),
          ),
          const SizedBox(height: AppDimensions.spacing16),
          Row(
            children: [
              Expanded(
                child: SecondaryButton(
                  text: 'AR 预览',
                  icon: Icons.view_in_ar,
                  onPressed: () => _showSnackBar('AR 预览'),
                ),
              ),
              const SizedBox(width: AppDimensions.spacing12),
              Expanded(
                child: PrimaryButton(
                  text: '详细介绍',
                  icon: Icons.info,
                  onPressed: () => _showSnackBar('查看详情'),
                ),
              ),
            ],
          ),
        ],
      ),
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

  void _toggleLoading() {
    setState(() {
      isLoading = !isLoading;
    });

    if (isLoading) {
      // 模拟加载 2 秒后自动停止
      Future.delayed(const Duration(seconds: 2), () {
        if (mounted) {
          setState(() {
            isLoading = false;
          });
          _showSnackBar('加载完成');
        }
      });
    }
  }
}
