/// 通票商品的**本地化价格**。
///
/// 付费墙此前根本不显示价格 —— 用户是在不知道多少钱的情况下点「获取通票」的。
/// 这既是转化问题,也是 Google Play 的合规要求(购买前必须清楚展示价格)。
///
/// ⚠️ **不要硬编码 "€7.99"**。Play 按地区返回本地化价格串(£7.99 / ¥1,200 /
/// $8.99),写死等于对绝大多数地区显示错误金额。拿不到价格就**整块不显示**,
/// 绝不显示假价格 —— 显示错的金额比不显示严重得多。
library;

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:in_app_purchase/in_app_purchase.dart';

import 'package:gomuseum_app/core/services/iap_service.dart';

/// 只查商品详情,**不订阅 purchaseStream**:付费墙只要一个价格串,
/// 购买全流程(初始化/验证/发权益)仍然只在权益页那一处实现。
final passPriceProvider = FutureProvider<String?>((ref) async {
  try {
    final iap = InAppPurchase.instance;
    if (!await iap.isAvailable()) return null;
    final res = await iap.queryProductDetails({IapService.kParisPass7d});
    if (res.error != null || res.productDetails.isEmpty) return null;
    return res.productDetails.first.price;
  } catch (_) {
    // 桌面/测试环境没有 IAP 插件。价格拿不到不该把付费墙打死。
    return null;
  }
});
