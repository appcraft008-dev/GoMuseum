/// GoMuseum 路由配置
library;

import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'package:gomuseum_app/core/router/app_shell.dart';
import 'package:gomuseum_app/features/home/presentation/pages/home_page.dart';
import 'package:gomuseum_app/features/recognition/presentation/pages/camera_page.dart';
import 'package:gomuseum_app/features/explore/presentation/pages/museum_page.dart';
import 'package:gomuseum_app/features/guide/presentation/pages/guide_page.dart';
import 'package:gomuseum_app/features/payment/presentation/pages/benefits_page.dart';
import 'package:gomuseum_app/features/explore/presentation/pages/explore_page.dart';
import 'package:gomuseum_app/features/history/presentation/pages/history_page.dart';
import 'package:gomuseum_app/features/settings/presentation/pages/settings_page.dart';
import 'package:gomuseum_app/features/auth/presentation/login_page.dart';
import 'package:gomuseum_app/features/auth/presentation/register_page.dart';
import 'package:gomuseum_app/features/auth/presentation/auth_provider.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

/// 路由配置提供者 - 带认证守卫
final goRouterProvider = Provider<GoRouter>((ref) {
  final authState = ref.watch(currentUserProvider);

  return GoRouter(
    initialLocation: '/',
    redirect: (context, state) {
      final isLoggedIn = authState.value != null;
      final isLoginRoute = state.uri.path == '/login';
      final isRegisterRoute = state.uri.path == '/register';
      final isPublicRoute = isLoginRoute || isRegisterRoute;

      // 未登录且访问受保护路由 → 跳转登录页
      if (!isLoggedIn && !isPublicRoute) {
        return '/login';
      }

      // 已登录且访问登录/注册页 → 跳转首页
      if (isLoggedIn && isPublicRoute) {
        return '/';
      }

      // 无需重定向
      return null;
    },
    refreshListenable: _GoRouterRefreshStream(ref),
    routes: [
      // 登录页（全屏）
      GoRoute(
        path: '/login',
        name: 'login',
        builder: (context, state) => const LoginPage(),
      ),

      // 注册页（全屏）
      GoRoute(
        path: '/register',
        name: 'register',
        builder: (context, state) => const RegisterPage(),
      ),
      // Shell路由 - 包含底部导航栏的页面
      ShellRoute(
        builder: (context, state, child) {
          // 根据路径确定当前索引（5项导航）
          // 0: 首页, 1: 探索, 2: 识别, 3: 足迹, 4: 设置
          int getCurrentIndex(String location) {
            if (location == '/') return 0; // 首页
            if (location.startsWith('/explore')) return 1; // 探索
            if (location.startsWith('/camera')) return 2; // 识别（不在shell中）
            if (location.startsWith('/history')) return 3; // 足迹
            if (location.startsWith('/settings')) return 4; // 设置
            return 0;
          }

          return AppShell(
            currentIndex: getCurrentIndex(state.uri.path),
            child: child,
          );
        },
        routes: [
          // 主页
          GoRoute(
            path: '/',
            name: 'home',
            pageBuilder: (context, state) => NoTransitionPage(
              child: const HomePage(),
            ),
          ),

          // 探索页
          GoRoute(
            path: '/explore',
            name: 'explore',
            pageBuilder: (context, state) => NoTransitionPage(
              child: const ExplorePage(),
            ),
          ),

          // 历史页
          GoRoute(
            path: '/history',
            name: 'history',
            pageBuilder: (context, state) => NoTransitionPage(
              child: const HistoryPage(),
            ),
          ),

          // 设置页
          GoRoute(
            path: '/settings',
            name: 'settings',
            pageBuilder: (context, state) => NoTransitionPage(
              child: const SettingsPage(),
            ),
          ),
        ],
      ),

      // 全屏页面 - 不包含底部导航栏
      // 相机页
      GoRoute(
        path: '/camera',
        name: 'camera',
        builder: (context, state) => const CameraPage(),
      ),

      // 讲解页（识别确认后进入）
      GoRoute(
        path: '/guide',
        name: 'guide',
        builder: (context, state) {
          final args = state.extra;
          if (args is! GuideArgs) {
            return const Scaffold(
              body: Center(child: Text('缺少讲解参数')),
            );
          }
          return GuidePage(args: args);
        },
      ),

      // 馆藏清单页
      GoRoute(
        path: '/museum/:slug',
        name: 'museum',
        builder: (context, state) =>
            MuseumPage(slug: state.pathParameters['slug'] ?? 'orsay'),
      ),

      // 升级 / 权益页
      GoRoute(
        path: '/benefits',
        name: 'benefits',
        builder: (context, state) => const BenefitsPage(),
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
});

/// Refresh stream for GoRouter to listen to auth state changes
class _GoRouterRefreshStream extends ChangeNotifier {
  _GoRouterRefreshStream(Ref ref) {
    ref.listen(currentUserProvider, (_, __) {
      notifyListeners();
    });
  }
}
