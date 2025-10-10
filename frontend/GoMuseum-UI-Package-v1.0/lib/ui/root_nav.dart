// lib/ui/root_nav.dart
import 'package:flutter/material.dart';
import '../theme/tokens.dart';

class RootNav extends StatefulWidget {
  const RootNav({super.key});
  @override
  State<RootNav> createState() => _RootNavState();
}

class _RootNavState extends State<RootNav> {
  int _index = 0;

  final _pages = const [
    Placeholder(), Placeholder(), SizedBox(), Placeholder(), Placeholder()
  ];

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: IndexedStack(index: _index == 2 ? 0 : _index, children: [
        _pages[0], _pages[1], _pages[0], _pages[3], _pages[4]
      ]),
      floatingActionButtonLocation: FloatingActionButtonLocation.centerDocked,
      floatingActionButton: _CaptureFAB(onTap: (){
        // TODO: push Capture Page
      }),
      bottomNavigationBar: BottomAppBar(
        height: 64,
        shape: const CircularNotchedRectangle(),
        notchMargin: 8,
        child: Row(
          mainAxisAlignment: MainAxisAlignment.spaceAround,
          children: [
            _NavItem(icon: Icons.home, label: 'Home', selected: _index==0, onTap: ()=>setState(()=>_index=0)),
            _NavItem(icon: Icons.explore, label: 'Explore', selected: _index==1, onTap: ()=>setState(()=>_index=1)),
            const SizedBox(width: 56),
            _NavItem(icon: Icons.bookmark_border, label: 'Footprints', selected: _index==3, onTap: ()=>setState(()=>_index=3)),
            _NavItem(icon: Icons.settings, label: 'Settings', selected: _index==4, onTap: ()=>setState(()=>_index=4)),
          ],
        ),
      ),
    );
  }
}

class _CaptureFAB extends StatelessWidget {
  final VoidCallback onTap;
  const _CaptureFAB({required this.onTap});
  @override
  Widget build(BuildContext context) {
    return FloatingActionButton(
      onPressed: onTap,
      shape: const CircleBorder(),
      backgroundColor: const Color(GMColors.ctaRecognize),
      child: const Icon(Icons.camera_alt, color: Colors.black),
    );
  }
}

class _NavItem extends StatelessWidget {
  final IconData icon; final String label; final bool selected; final VoidCallback onTap;
  const _NavItem({required this.icon, required this.label, required this.selected, required this.onTap});
  @override
  Widget build(BuildContext context) {
    final color = selected ? const Color(GMColors.brandPrimary) : const Color(GMColors.textSecondary);
    return InkWell(onTap: onTap, child: SizedBox(width: 56, child: Column(
      mainAxisAlignment: MainAxisAlignment.center, children: [
        Icon(icon, size: 22, color: color), const SizedBox(height: 4),
        Text(label, style: TextStyle(fontSize: 11, color: color))
    ])));
  }
}
