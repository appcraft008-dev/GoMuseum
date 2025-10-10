/// GoMuseum 路由配置
library;

import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'package:gomuseum_app/features/home/presentation/pages/home_page.dart';
import 'package:gomuseum_app/features/recognition/presentation/pages/camera_page.dart';
import 'package:gomuseum_app/features/recognition/presentation/pages/result_page.dart';
import 'package:gomuseum_app/features/explore/presentation/pages/explore_page.dart';
import 'package:gomuseum_app/features/history/presentation/pages/history_page.dart';
import 'package:gomuseum_app/features/settings/presentation/pages/settings_page.dart';

/// 路由配置
final goRouter = GoRouter(
  initialLocation: '/',
  routes: [
    // 主页
    GoRoute(
      path: '/',
      name: 'home',
      builder: (context, state) => const HomePage(),
    ),
    
    // 相机页
    GoRoute(
      path: '/camera',
      name: 'camera',
      builder: (context, state) => const CameraPage(),
    ),
    
    // 识别结果页
    GoRoute(
      path: '/result/:id',
      name: 'result',
      builder: (context, state) {
        final id = state.pathParameters['id'] ?? '';
        return ResultPage(artworkId: id);
      },
    ),
    
    // 探索页
    GoRoute(
      path: '/explore',
      name: 'explore',
      builder: (context, state) => const ExplorePage(),
    ),
    
    // 历史页
    GoRoute(
      path: '/history',
      name: 'history',
      builder: (context, state) => const HistoryPage(),
    ),
    
    // 设置页
    GoRoute(
      path: '/settings',
      name: 'settings',
      builder: (context, state) => const SettingsPage(),
    ),
  ],
  
  // 错误处理
  errorBuilder: (context, state) => Scaffold(
    appBar: AppBar(title: const Text('页面未找到')),
    body: Center(
      child: Text('错误: ${state.error}'),
    ),
  ),
);
