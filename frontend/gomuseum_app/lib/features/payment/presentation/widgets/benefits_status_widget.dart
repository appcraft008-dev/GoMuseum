import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../providers/benefits_provider.dart';

/// 权益状态Widget
class BenefitsStatusWidget extends ConsumerWidget {
  const BenefitsStatusWidget({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final benefitsAsync = ref.watch(benefitsStateProvider);

    return benefitsAsync.when(
      data: (benefits) => Card(
        margin: const EdgeInsets.all(16),
        elevation: 2,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(12),
        ),
        child: Padding(
          padding: const EdgeInsets.all(16),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                children: [
                  Icon(
                    Icons.card_membership,
                    color: Theme.of(context).primaryColor,
                    size: 28,
                  ),
                  const SizedBox(width: 12),
                  Text(
                    '我的权益',
                    style: Theme.of(context).textTheme.titleLarge?.copyWith(
                          fontWeight: FontWeight.bold,
                        ),
                  ),
                ],
              ),
              const Divider(height: 24),
              _buildBenefitItem(
                context,
                icon: Icons.image_search,
                title: '识别次数',
                value: benefits.recognitionQuota > 0
                    ? '${benefits.recognitionQuota}次'
                    : '无剩余',
                isActive: benefits.recognitionQuota > 0,
              ),
              const SizedBox(height: 12),
              _buildBenefitItem(
                context,
                icon: Icons.today,
                title: '日卡',
                value: benefits.dayPassActive
                    ? _formatExpiry(benefits.dayPassExpiresAt)
                    : '未激活',
                isActive: benefits.dayPassActive,
              ),
              const SizedBox(height: 12),
              _buildBenefitItem(
                context,
                icon: Icons.star,
                title: '高级会员',
                value: benefits.isPremium
                    ? _formatExpiry(benefits.premiumExpiresAt)
                    : '未开通',
                isActive: benefits.isPremium,
              ),
              const SizedBox(height: 16),
              if (!benefits.hasAccess)
                Container(
                  padding: const EdgeInsets.all(12),
                  decoration: BoxDecoration(
                    color: Colors.orange[50],
                    borderRadius: BorderRadius.circular(8),
                    border: Border.all(color: Colors.orange[200]!),
                  ),
                  child: Row(
                    children: [
                      Icon(Icons.info_outline, color: Colors.orange[700]),
                      const SizedBox(width: 8),
                      Expanded(
                        child: Text(
                          '您当前无识别权限，请购买识别包、日卡或开通会员',
                          style: TextStyle(
                            color: Colors.orange[700],
                            fontSize: 13,
                          ),
                        ),
                      ),
                    ],
                  ),
                ),
            ],
          ),
        ),
      ),
      loading: () => const Card(
        margin: EdgeInsets.all(16),
        child: Padding(
          padding: EdgeInsets.all(32),
          child: Center(
            child: CircularProgressIndicator(),
          ),
        ),
      ),
      error: (error, _) => Card(
        margin: const EdgeInsets.all(16),
        child: Padding(
          padding: const EdgeInsets.all(16),
          child: Column(
            children: [
              Icon(Icons.error_outline, color: Colors.red[400], size: 48),
              const SizedBox(height: 12),
              Text(
                '加载权益失败',
                style: TextStyle(color: Colors.red[400]),
              ),
              const SizedBox(height: 8),
              TextButton(
                onPressed: () =>
                    ref.read(benefitsStateProvider.notifier).refresh(),
                child: const Text('重试'),
              ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildBenefitItem(
    BuildContext context, {
    required IconData icon,
    required String title,
    required String value,
    required bool isActive,
  }) {
    return Row(
      children: [
        Container(
          padding: const EdgeInsets.all(8),
          decoration: BoxDecoration(
            color: isActive
                ? Theme.of(context).primaryColor.withOpacity(0.1)
                : Colors.grey[200],
            borderRadius: BorderRadius.circular(8),
          ),
          child: Icon(
            icon,
            color: isActive ? Theme.of(context).primaryColor : Colors.grey,
            size: 20,
          ),
        ),
        const SizedBox(width: 12),
        Expanded(
          child: Text(
            title,
            style: Theme.of(context).textTheme.bodyLarge,
          ),
        ),
        Text(
          value,
          style: Theme.of(context).textTheme.bodyLarge?.copyWith(
                fontWeight: FontWeight.bold,
                color: isActive
                    ? Theme.of(context).primaryColor
                    : Colors.grey[600],
              ),
        ),
      ],
    );
  }

  String _formatExpiry(DateTime? expiry) {
    if (expiry == null) return '长期有效';
    final now = DateTime.now();
    final difference = expiry.difference(now);

    if (difference.inDays > 0) {
      return '剩余${difference.inDays}天';
    } else if (difference.inHours > 0) {
      return '剩余${difference.inHours}小时';
    } else {
      return '即将过期';
    }
  }
}
