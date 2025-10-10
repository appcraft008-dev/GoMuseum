// lib/widgets/subscription_modal.dart
import 'package:flutter/material.dart';
import '../theme/tokens.dart';

Future<void> showSubscriptionModal(BuildContext context) async {
  int selected = 1;
  await showDialog(
    context: context,
    barrierDismissible: true,
    builder: (_) => StatefulBuilder(builder: (context, setState) {
      return Dialog(
        insetPadding: const EdgeInsets.symmetric(horizontal: 20, vertical: 24),
        child: Container(
          padding: const EdgeInsets.all(GMSpace.s6),
          decoration: const BoxDecoration(
            borderRadius: BorderRadius.all(Radius.circular(GMRadius.lg)),
            color: Colors.white,
          ),
          child: Column(mainAxisSize: MainAxisSize.min, children: [
            const Text('Get Unlimited Access', style: TextStyle(fontSize: 20, fontWeight: FontWeight.w700)),
            const SizedBox(height: GMSpace.s4),
            ToggleButtons(
              isSelected: [selected==0, selected==1, selected==2],
              borderRadius: const BorderRadius.all(Radius.circular(GMRadius.pill)),
              onPressed: (i) => setState(()=>selected=i),
              children: const [
                Padding(padding: EdgeInsets.symmetric(horizontal: 12), child: Text('Weekly')),
                Padding(padding: EdgeInsets.symmetric(horizontal: 12), child: Text('Monthly')),
                Padding(padding: EdgeInsets.symmetric(horizontal: 12), child: Text('Yearly')),
              ],
            ),
            const SizedBox(height: GMSpace.s4),
            const _PlanCard(title: 'Unlimited recognition', subtitle: 'Faster answers • Premium voices'),
            const SizedBox(height: GMSpace.s4),
            Row(children: [
              Expanded(
                child: ElevatedButton(
                  onPressed: (){
                    // TODO: IAP/GPB by selected SKU
                  },
                  style: ElevatedButton.styleFrom(
                    backgroundColor: Color(GMColors.brandAccent),
                    foregroundColor: Colors.white,
                    minimumSize: const Size.fromHeight(48),
                    shape: const RoundedRectangleBorder(borderRadius: BorderRadius.all(Radius.circular(GMRadius.md)))
                  ),
                  child: const Text('Start Subscription'),
                ),
              ),
            ]),
            TextButton(onPressed: (){
              // TODO: Restore purchases
            }, child: const Text('Restore Purchases'))
          ]),
        ),
      );
    }),
  );
}

class _PlanCard extends StatelessWidget {
  final String title; final String subtitle;
  const _PlanCard({required this.title, required this.subtitle});
  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(GMSpace.s4),
      decoration: const BoxDecoration(
        color: Color(0xFFFEFEFE),
        borderRadius: BorderRadius.all(Radius.circular(GMRadius.md)),
        boxShadow: [BoxShadow(blurRadius: 16, offset: Offset(0,6), color: Color(0x12000000))]
      ),
      child: Row(children: [
        const Icon(Icons.workspace_premium),
        const SizedBox(width: GMSpace.s3),
        const Expanded(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Text('Unlimited recognition', style: TextStyle(fontWeight: FontWeight.w600)),
          SizedBox(height: 4),
          Text('Faster answers • Premium voices', style: TextStyle(color: Color(GMColors.textSecondary))),
        ]))
      ]),
    );
  }
}
