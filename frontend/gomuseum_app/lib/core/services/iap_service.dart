import 'dart:async';
import 'package:flutter/foundation.dart';
import 'package:in_app_purchase/in_app_purchase.dart';

/// 应用内购买服务
class IapService {
  final InAppPurchase _iap = InAppPurchase.instance;

  StreamSubscription<List<PurchaseDetails>>? _subscription;
  List<ProductDetails> _products = [];
  bool _available = false;

  /// 巴黎 7 日通票(€7.99)——**唯一在售商品**,必须与 Play Console 的商品 ID
  /// 和后端 `entitlement_service.PARIS_PASS_7D` 三处字面量一致。
  ///
  /// 类型是 **Consumable**(不是订阅、不是 Non-consumable):票会到期,用户
  /// 下次来巴黎要能再买一张;Non-consumable 买过就永远"已拥有"、无法复购。
  ///
  /// ⚠️ 曾在售的 recognition_pack_10 / day_pass / premium_annual 已随收费定案废弃
  /// (不按馆、不做差价升级——Play 无原生补差价,自做=收错钱风险)。后端仍认老商品
  /// 以免破已装 App,但新版不再展示、不再引导购买。
  static const String kParisPass7d = 'paris_pass_7d';

  /// 所有商品ID
  static const List<String> kProductIds = [kParisPass7d];

  /// 是否可用
  bool get isAvailable => _available;

  /// 商品列表
  List<ProductDetails> get products => _products;

  /// 初始化IAP
  Future<bool> initialize({
    /// 返回 true 表示后端已验证并发放权益,才会 completePurchase。
    required Future<bool> Function(PurchaseDetails) onPurchaseUpdated,
    Function(IapError)? onError,
  }) async {
    _available = await _iap.isAvailable();
    if (!_available) {
      debugPrint('应用内购买不可用');
      return false;
    }

    // 监听购买更新
    _subscription = _iap.purchaseStream.listen(
      (purchases) {
        for (final purchase in purchases) {
          _handlePurchaseUpdate(purchase, onPurchaseUpdated, onError);
        }
      },
      onError: (error) {
        debugPrint('购买流错误: $error');
        onError?.call(IapError(message: error.toString()));
      },
    );

    // 加载商品
    await loadProducts();

    return true;
  }

  /// 加载商品列表
  Future<void> loadProducts() async {
    if (!_available) return;

    try {
      final response = await _iap.queryProductDetails(kProductIds.toSet());

      if (response.error != null) {
        debugPrint('查询商品失败: ${response.error}');
        return;
      }

      _products = response.productDetails;
      debugPrint('已加载 ${_products.length} 个商品');
    } catch (e) {
      debugPrint('加载商品异常: $e');
    }
  }

  /// 购买商品
  ///
  /// [productId] - 商品ID
  Future<bool> purchaseProduct(String productId) async {
    if (!_available) {
      debugPrint('IAP不可用');
      return false;
    }

    final product = _products.firstWhere(
      (p) => p.id == productId,
      orElse: () => throw Exception('商品不存在: $productId'),
    );

    final purchaseParam = PurchaseParam(productDetails: product);

    try {
      // 通票是 Consumable:到期后用户要能再买一张(见 kParisPass7d 注释)
      return await _iap.buyConsumable(purchaseParam: purchaseParam);
    } catch (e) {
      debugPrint('购买失败: $e');
      return false;
    }
  }

  /// 恢复购买
  Future<void> restorePurchases() async {
    if (!_available) return;

    try {
      await _iap.restorePurchases();
    } catch (e) {
      debugPrint('恢复购买失败: $e');
      rethrow;
    }
  }

  /// 处理购买更新
  void _handlePurchaseUpdate(
    PurchaseDetails purchase,
    Future<bool> Function(PurchaseDetails) onPurchaseUpdated,
    Function(IapError)? onError,
  ) {
    debugPrint('购买状态: ${purchase.status}');

    switch (purchase.status) {
      case PurchaseStatus.pending:
        // 购买等待中
        break;
      case PurchaseStatus.purchased:
      case PurchaseStatus.restored:
        // 购买成功或已恢复
        _verifyAndDeliverProduct(purchase, onPurchaseUpdated, onError);
        break;
      case PurchaseStatus.error:
        // 购买失败
        onError?.call(IapError(
          message: purchase.error?.message ?? '购买失败',
          code: purchase.error?.code,
        ));
        _iap.completePurchase(purchase);
        break;
      case PurchaseStatus.canceled:
        // 用户取消
        debugPrint('用户取消购买');
        _iap.completePurchase(purchase);
        break;
    }
  }

  /// 验证并交付商品
  ///
  /// ⚠️ **必须等后端验证成功再 completePurchase**。通票是 Consumable——
  /// 一旦 complete 就被消耗,`restorePurchases` 再也拿不回来(消耗型商品不在
  /// 恢复列表里)。此前是"回调后端验证但不等结果,立刻 complete":验证那一刻
  /// 网络抖一下,用户付了钱、后端没发权益,且**永久无法补发**。
  ///
  /// 验证失败就把它留在 pending —— 下次启动 purchaseStream 会重新投递,自动重试。
  Future<void> _verifyAndDeliverProduct(
    PurchaseDetails purchase,
    Future<bool> Function(PurchaseDetails) onPurchaseUpdated,
    Function(IapError)? onError,
  ) async {
    try {
      final delivered = await onPurchaseUpdated(purchase);
      if (!delivered) {
        debugPrint('后端验证未通过,保留 pending 待下次启动重试');
        onError?.call(IapError(message: '购买验证未完成,重启应用会自动重试'));
        return;
      }
      if (purchase.pendingCompletePurchase) {
        await _iap.completePurchase(purchase);
      }
    } catch (e) {
      // 同样不 complete:留着重试,别把用户的钱吞掉
      debugPrint('交付商品失败: $e');
      onError?.call(IapError(message: '交付失败: $e'));
    }
  }

  /// 释放资源
  Future<void> dispose() async {
    await _subscription?.cancel();
  }
}

/// IAP错误
class IapError {
  final String message;
  final String? code;

  IapError({required this.message, this.code});

  @override
  String toString() => code != null ? '[$code] $message' : message;
}
