import 'dart:async';
import 'package:flutter/foundation.dart';
import 'package:in_app_purchase/in_app_purchase.dart';

/// 应用内购买服务
class IapService {
  final InAppPurchase _iap = InAppPurchase.instance;

  StreamSubscription<List<PurchaseDetails>>? _subscription;
  List<ProductDetails> _products = [];
  bool _available = false;

  /// 商品ID定义
  static const String kRecognitionPack10 = 'com.gomuseum.recognition_pack_10';
  static const String kDayPass = 'com.gomuseum.day_pass';
  static const String kPremiumAnnual = 'com.gomuseum.premium_annual';

  /// 所有商品ID
  static const List<String> kProductIds = [
    kRecognitionPack10,
    kDayPass,
    kPremiumAnnual,
  ];

  /// 是否可用
  bool get isAvailable => _available;

  /// 商品列表
  List<ProductDetails> get products => _products;

  /// 初始化IAP
  Future<bool> initialize({
    required Function(PurchaseDetails) onPurchaseUpdated,
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
      if (product.id == kPremiumAnnual) {
        // 订阅类型
        return await _iap.buyNonConsumable(purchaseParam: purchaseParam);
      } else {
        // 消耗型商品
        return await _iap.buyConsumable(purchaseParam: purchaseParam);
      }
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
    Function(PurchaseDetails) onPurchaseUpdated,
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
  Future<void> _verifyAndDeliverProduct(
    PurchaseDetails purchase,
    Function(PurchaseDetails) onPurchaseUpdated,
    Function(IapError)? onError,
  ) async {
    // TODO: 在生产环境中，应该将purchase.verificationData发送到后端验证

    try {
      // 验证成功，交付商品
      onPurchaseUpdated(purchase);

      // 完成购买
      if (purchase.pendingCompletePurchase) {
        await _iap.completePurchase(purchase);
      }
    } catch (e) {
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
