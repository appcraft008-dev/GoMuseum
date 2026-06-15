import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:easy_localization/easy_localization.dart';
import 'package:in_app_purchase/in_app_purchase.dart';
import '../../core/services/iap_service.dart';
import '../../theme/tokens.dart';

class SubscriptionModal extends ConsumerStatefulWidget {
  const SubscriptionModal({super.key});
  @override
  ConsumerState<SubscriptionModal> createState() => _SubscriptionModalState();
}

class _SubscriptionModalState extends ConsumerState<SubscriptionModal> {
  late final IapService _iapService;
  bool _isLoading = true;
  bool _isPurchasing = false;

  @override
  void initState() {
    super.initState();
    _iapService = IapService();
    _initializeIap();
  }

  Future<void> _initializeIap() async {
    await _iapService.initialize(
      onPurchaseUpdated: (purchase) {
        Navigator.of(context).pop(true);
      },
    );
    setState(() => _isLoading = false);
  }

  @override
  Widget build(BuildContext context) {
    return Container(
      decoration: const BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.vertical(top: Radius.circular(20)),
      ),
      padding: const EdgeInsets.all(24),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          const Text('Subscribe',
              style: TextStyle(fontSize: 24, fontWeight: FontWeight.bold)),
          const SizedBox(height: 24),
          if (_isLoading) const CircularProgressIndicator(),
          if (!_isLoading) ..._iapService.products.map((p) => _buildProduct(p)),
          TextButton(
              onPressed: () => Navigator.pop(context),
              child: const Text('Close')),
        ],
      ),
    );
  }

  Widget _buildProduct(prod) {
    return Card(
      child: ListTile(
        title: Text(prod.title),
        subtitle: Text(prod.description),
        trailing: Text(prod.price),
        onTap: () => _iapService.purchaseProduct(prod.id),
      ),
    );
  }
}

Future<bool?> showSubscriptionModal(BuildContext context) {
  return showModalBottomSheet<bool>(
    context: context,
    isScrollControlled: true,
    backgroundColor: Colors.transparent,
    builder: (context) => const SubscriptionModal(),
  );
}
