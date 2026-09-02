import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:gomuseum_app/features/payment/data/entitlements.dart';
import 'package:gomuseum_app/l10n/app_localizations.dart';
import '../providers/benefits_provider.dart';

/// 权益状态Widget
///
/// ⚠️ 取主色一律用 `colorScheme.primary`,**别用 `Theme.of(context).primaryColor`**:
/// ThemeData 在深色主题下把 primaryColor 默认成 `colorScheme.surface`
/// (flutter/src/material/theme_data.dart:447 `primarySurfaceColor`),
/// 那正是本卡片的背景色 —— 文字和图标会与底色同色、整个看不见。
/// 2026-09-02 真机上「识别次数」的数值就这样凭空消失了。
class BenefitsStatusWidget extends ConsumerWidget {
  const BenefitsStatusWidget({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final benefitsAsync = ref.watch(benefitsStateProvider);
    final ent = ref.watch(entitlementsProvider).value;

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
                    color: Theme.of(context).colorScheme.primary,
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
              // 通票状态。真相源是 `/entitlements` 的 state —— **不要**从 user_benefits
              // 的额度账里推断(那是第二套真相源,App 显示"会员"而后端 402 就是这么来的)。
              // 缺了这一行,已付费用户在这一页只看得到「识别次数」和一个商品列表,
              // 全程没有一处确认票在手上(2026-09-02 用户提出)。
              if (ent != null && (ent.isActive || ent.isPurchasedNotActivated))
                _buildBenefitItem(
                  context,
                  icon: Icons.confirmation_number,
                  title: ent.isActive
                      ? AppLocalizations.of(context)!.passActive
                      : AppLocalizations.of(context)!.passPendingActivation,
                  value: ent.isActive && ent.expiresAt != null
                      ? AppLocalizations.of(context)!
                          .passExpiresOn(ent.expiresAt!)
                      : AppLocalizations.of(context)!.passActivateHint,
                  isActive: true,
                ),
              if (ent != null && (ent.isActive || ent.isPurchasedNotActivated))
                const SizedBox(height: 12),
              _buildBenefitItem(
                context,
                icon: Icons.image_search,
                title: '识别次数',
                // 通票期间识别不限次 —— 照 user_benefits 的余额渲染会在
                // 「通票生效中」旁边写一个次数,像是仍有上限。
                value: ent != null && ent.isActive
                    ? AppLocalizations.of(context)!.unlimited
                    : benefits.recognitionQuota > 0
                        ? '${benefits.recognitionQuota}次'
                        : '无剩余',
                isActive: (ent != null && ent.isActive) ||
                    benefits.recognitionQuota > 0,
              ),
              // ⚠️ 这里曾显示「日卡」「高级会员」两行,数据来自 user_benefits 的
              // is_premium / day_pass_active —— 那是**第二套权益真相源**,已随老商品
              // 下线移除。通票状态要显示的话,读 `/entitlements` 的 `can`,别再从
              // 额度账里推断(App 显示"会员"而后端 402 就是这么来的)。
              const SizedBox(height: 16),
              // 有通票就别再劝购 —— `hasAccess` 来自 user_benefits 那套老额度账,
              // 它不认通票,不挡的话已付费用户会看到「买通票可继续使用」。
              if (!benefits.hasAccess && !(ent?.isActive ?? false))
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
                          '免费识别次数已用完，购买通票可继续使用',
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
                ? Theme.of(context).colorScheme.primary.withOpacity(0.1)
                : Colors.grey[200],
            borderRadius: BorderRadius.circular(8),
          ),
          child: Icon(
            icon,
            color:
                isActive ? Theme.of(context).colorScheme.primary : Colors.grey,
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
                    ? Theme.of(context).colorScheme.primary
                    : Colors.grey[600],
              ),
        ),
      ],
    );
  }
}
