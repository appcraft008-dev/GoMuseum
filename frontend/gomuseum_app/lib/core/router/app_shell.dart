/// GoMuseum App Shell - 管理底部导航的主容器
library;

import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'package:gomuseum_app/ui/gm/gm_nav_scan.dart';

/// App Shell - 包含底部导航栏的主容器
class AppShell extends StatefulWidget {
  final Widget child;
  final int currentIndex;

  const AppShell({
    super.key,
    required this.child,
    this.currentIndex = 0,
  });

  @override
  State<AppShell> createState() => _AppShellState();
}

class _AppShellState extends State<AppShell> {
  late int _currentIndex;

  @override
  void initState() {
    super.initState();
    _currentIndex = widget.currentIndex;
  }

  @override
  void didUpdateWidget(AppShell oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (widget.currentIndex != oldWidget.currentIndex) {
      setState(() {
        _currentIndex = widget.currentIndex;
      });
    }
  }

  void _onNavTap(int index) {
    if (index == _currentIndex && index != 2) return; // 避免重复导航（识别除外，可重复点击）

    setState(() {
      _currentIndex = index;
    });

    switch (index) {
      case 0: // 首页
        context.go('/');
        break;
      case 1: // 探索
        context.go('/explore');
        break;
      case 2: // 识别 (中间FAB)
        context.push('/camera');
        break;
      case 3: // 足迹（原历史）
        context.go('/history');
        break;
      case 4: // 设置
        context.go('/settings');
        break;
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: widget.child,
      bottomNavigationBar: GmNavScan(
        currentIndex: _currentIndex,
        onTap: _onNavTap,
      ),
    );
  }
}
