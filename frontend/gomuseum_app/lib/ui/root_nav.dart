import 'package:flutter/material.dart';
import '../l10n/app_localizations.dart';
import '../theme/tokens.dart';
import 'pages/home_page.dart';
import 'pages/explore_page.dart';
import 'pages/capture_page.dart';
import 'pages/footprints_page.dart';
import 'pages/settings_page.dart';

class RootNav extends StatefulWidget {
  const RootNav({super.key});
  @override
  State<RootNav> createState() => _RootNavState();
}

class _RootNavState extends State<RootNav> {
  int _index = 0;

  final _pages = const [
    HomePage(), // 0
    ExplorePage(), // 1
    SizedBox(), // 2 - FAB占位
    FootprintsPage(), // 3
    SettingsPage(), // 4
  ];

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context)!;

    return Scaffold(
      body: IndexedStack(
        index: _index == 2 ? 0 : _index,
        children: [_pages[0], _pages[1], _pages[0], _pages[3], _pages[4]],
      ),
      floatingActionButtonLocation: FloatingActionButtonLocation.centerDocked,
      floatingActionButton: _CaptureFAB(
        onTap: () {
          Navigator.push(
            context,
            MaterialPageRoute(builder: (_) => const CapturePage()),
          );
        },
      ),
      bottomNavigationBar: BottomAppBar(
        height: 64,
        shape: const CircularNotchedRectangle(),
        notchMargin: 8,
        child: Row(
          mainAxisAlignment: MainAxisAlignment.spaceAround,
          children: [
            _NavItem(
              icon: Icons.home,
              label: l10n.home,
              selected: _index == 0,
              onTap: () => setState(() => _index = 0),
            ),
            _NavItem(
              icon: Icons.explore,
              label: l10n.explore,
              selected: _index == 1,
              onTap: () => setState(() => _index = 1),
            ),
            const SizedBox(width: 56),
            _NavItem(
              icon: Icons.bookmark_border,
              label: l10n.footprints,
              selected: _index == 3,
              onTap: () => setState(() => _index = 3),
            ),
            _NavItem(
              icon: Icons.settings,
              label: l10n.settings,
              selected: _index == 4,
              onTap: () => setState(() => _index = 4),
            ),
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
  final IconData icon;
  final String label;
  final bool selected;
  final VoidCallback onTap;

  const _NavItem({
    required this.icon,
    required this.label,
    required this.selected,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    final color = selected
        ? const Color(GMColors.brandPrimary)
        : const Color(GMColors.textSecondary);
    return InkWell(
      onTap: onTap,
      child: SizedBox(
        width: 56,
        child: Column(
          mainAxisSize: MainAxisSize.min,
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(icon, size: 22, color: color),
            const SizedBox(height: 2),
            Text(
              label,
              style: TextStyle(fontSize: 10, color: color, height: 1.0),
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
            ),
          ],
        ),
      ),
    );
  }
}
