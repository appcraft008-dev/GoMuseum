import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:in_app_purchase/in_app_purchase.dart';
import '../../../../core/services/iap_service.dart';
import '../providers/benefits_provider.dart';
import '../widgets/benefits_status_widget.dart';
import '../widgets/product_card.dart';

/// 权益与购买页面
class BenefitsPage extends ConsumerStatefulWidget {
  const BenefitsPage({super.key});

  @override
  ConsumerState<BenefitsPage> createState() => _BenefitsPageState();
}

class _BenefitsPageState extends ConsumerState<BenefitsPage> {
  late final IapService _iapService;
  bool _isLoading = true;
  bool _isPurchasing = false;
  String? _purchasingProductId;

  @override
  void initState() {
    super.initState();
    _iapService = IapService();
    _initializeIap();
  }

  Future<void> _initializeIap() async {
    final success = await _iapService.initialize(
      onPurchaseUpdated: _handlePurchaseUpdate,
      onError: (error) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('购买错误: ${error.message}')),
        );
        setState(() {
          _isPurchasing = false;
          _purchasingProductId = null;
        });
      },
    );

    if (!success) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('应用内购买不可用')),
        );
      }
    }

    setState(() => _isLoading = false);
  }

  void _handlePurchaseUpdate(PurchaseDetails purchase) async {
    if (purchase.status == PurchaseStatus.purchased ||
        purchase.status == PurchaseStatus.restored) {
      // 验证购买并更新权益
      final success = await ref
          .read(benefitsStateProvider.notifier)
          .verifyAndUpdateBenefits(purchase);

      if (mounted) {
        if (success) {
          ScaffoldMessenger.of(context).showSnackBar(
            const SnackBar(
              content: Text('购买成功！权益已更新'),
              backgroundColor: Colors.green,
            ),
          );
        } else {
          ScaffoldMessenger.of(context).showSnackBar(
            const SnackBar(
              content: Text('购买验证失败，请联系客服'),
              backgroundColor: Colors.red,
            ),
          );
        }
      }
    }

    setState(() {
      _isPurchasing = false;
      _purchasingProductId = null;
    });
  }

  Future<void> _purchaseProduct(String productId) async {
    setState(() {
      _isPurchasing = true;
      _purchasingProductId = productId;
    });

    final success = await _iapService.purchaseProduct(productId);

    if (!success) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('购买失败，请重试')),
        );
      }
      setState(() {
        _isPurchasing = false;
        _purchasingProductId = null;
      });
    }
  }

  Future<void> _restorePurchases() async {
    try {
      await _iapService.restorePurchases();
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('正在恢复购买...')),
        );
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('恢复购买失败: $e')),
        );
      }
    }
  }

  @override
  void dispose() {
    _iapService.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('我的权益'),
        actions: [
          IconButton(
            icon: const Icon(Icons.restore),
            onPressed: _isLoading ? null : _restorePurchases,
            tooltip: '恢复购买',
          ),
          IconButton(
            icon: const Icon(Icons.refresh),
            onPressed: () =>
                ref.read(benefitsStateProvider.notifier).refresh(),
            tooltip: '刷新',
          ),
        ],
      ),
      body: RefreshIndicator(
        onRefresh: () async {
          await ref.read(benefitsStateProvider.notifier).refresh();
        },
        child: ListView(
          children: [
            // 权益状态卡片
            const BenefitsStatusWidget(),

            // 分隔线
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
              child: Row(
                children: [
                  Expanded(child: Divider(color: Colors.grey[300])),
                  Padding(
                    padding: const EdgeInsets.symmetric(horizontal: 16),
                    child: Text(
                      '购买商品',
                      style: Theme.of(context).textTheme.titleMedium?.copyWith(
                            color: Colors.grey[600],
                          ),
                    ),
                  ),
                  Expanded(child: Divider(color: Colors.grey[300])),
                ],
              ),
            ),

            // 商品列表
            if (_isLoading)
              const Center(
                child: Padding(
                  padding: EdgeInsets.all(32),
                  child: CircularProgressIndicator(),
                ),
              )
            else if (_iapService.products.isEmpty)
              Center(
                child: Padding(
                  padding: const EdgeInsets.all(32),
                  child: Column(
                    children: [
                      Icon(Icons.shopping_bag_outlined,
                          size: 64, color: Colors.grey[400]),
                      const SizedBox(height: 16),
                      Text(
                        '暂无可用商品',
                        style: TextStyle(color: Colors.grey[600]),
                      ),
                    ],
                  ),
                ),
              )
            else
              ..._iapService.products.map((product) {
                final isProductPurchasing =
                    _isPurchasing && _purchasingProductId == product.id;
                return ProductCard(
                  product: product,
                  isLoading: isProductPurchasing,
                  onTap: () => _purchaseProduct(product.id),
                );
              }),

            // 底部说明
            Padding(
              padding: const EdgeInsets.all(16),
              child: Column(
                children: [
                  const SizedBox(height: 16),
                  Text(
                    '购买说明',
                    style: Theme.of(context).textTheme.titleMedium?.copyWith(
                          fontWeight: FontWeight.bold,
                        ),
                  ),
                  const SizedBox(height: 8),
                  Text(
                    '• 识别包：一次性购买，立即获得指定识别次数\n'
                    '• 日卡：24小时内无限次识别\n'
                    '• 年度会员：一年内无限次识别，享受所有高级功能',
                    style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                          color: Colors.grey[600],
                        ),
                  ),
                  const SizedBox(height: 16),
                  Text(
                    '购买完成后，权益将自动同步到您的设备',
                    style: Theme.of(context).textTheme.bodySmall?.copyWith(
                          color: Colors.grey[500],
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
