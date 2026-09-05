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
import 'package:gomuseum_app/features/auth/domain/user.dart';
import 'package:gomuseum_app/features/auth/presentation/auth_provider.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

/// 「我是主动来换身份的」标记。带上它去 `/login` 或 `/register`，
/// 守卫才不会把已登录的人（包括游客）弹回首页。
///
/// 用路由参数而不是用户身份来表达意图：冷启动时守卫会先把人弹到登录页
/// （登录态还在加载），那次到达**不是**用户的意图；身份判据分不出这两者。
const kUpgradeParam = 'upgrade';

/// 带转正意图的登录页地址。三个购买链路入口都用它。
const kLoginToUpgrade = '/login?$kUpgradeParam=1';

/// 认证守卫的判断本身（纯函数，与 go_router / BuildContext 无关）。
///
/// 抽出来是为了能真测到它：整个 GoRouter 起来要拉起所有页面和它们的
/// provider，那种测试很容易变成"跑通了就算过"，而这里要钉的恰恰是几条
/// 具体的分支。见 `test/core/router/auth_guard_test.dart`。
///
/// 返回 null 表示不重定向。
String? authRedirect({
  required User? user,
  required String path,
  bool upgrading = false,
}) {
  final isLoggedIn = user != null;
  final isPublicRoute = path == '/login' || path == '/register';

  // 未登录且访问受保护路由 → 跳转登录页
  if (!isLoggedIn && !isPublicRoute) {
    return '/login';
  }

  // 已登录还停在登录/注册页 → 回首页。
  //
  // **除非他是主动来换身份的**（[upgrading]，即 `?upgrade=1`）：
  // 游客点「登录后购买」正是要去转正 —— 把他弹回首页，游客就**永远买不了票**
  // （通票挂账号，所以游客不许直接买，按钮才写「登录后购买」）。
  // 而这条重定向发生在 `push('/login')` 期间，被重定向到 shell 路由 `/`
  // 会渲染成一屏只剩底栏的黑屏，用户连"被弹回来了"都看不出来。
  //
  // ⚠️ **判据必须是「这次导航想干什么」，不能是「这个用户是不是游客」。**
  // 曾经按身份判（游客一律放行），结果冷启动就废了：`AuthNotifier` 初始是
  // loading，守卫第一次跑时 user 还是 null → 弹到 /login；等登录态加载完，
  // 按身份判就不再把游客送回首页 —— 游客**每次开 App 都卡在登录页**，
  // 而登录页又刚好把游客按钮藏了，等于锁在门外。
  // 冷启动那次弹过来根本不是用户的意图，身份判据分不出这两种到达方式。
  // 2026-09-05 真机发现。
  if (isLoggedIn && isPublicRoute && !upgrading) {
    return '/';
  }

  // 无需重定向
  return null;
}

/// 路由配置提供者 - 带认证守卫
final goRouterProvider = Provider<GoRouter>((ref) {
  return GoRouter(
    initialLocation: '/',
    redirect: (context, state) {
      // 登录态在 redirect 里**读**、不在 provider 体里 watch:watch 会让每次
      // 登录态变化都重建整个 GoRouter,把当前位置一起丢掉(点"注册"的瞬间就被
      // 弹回登录页)。刷新由下面的 refreshListenable 负责,那才是 go_router
      // 设计的入口。
      //
      // `valueOrNull` 而非 `value`:AsyncError 的 `.value` 会 rethrow,在
      // provider build 期抛出就是 release 下的整屏灰。这里读不到登录态时
      // 一律按"未登录"处理 —— 最坏是多登一次,而不是死一个 App。
      return authRedirect(
        user: ref.read(currentUserProvider).valueOrNull,
        path: state.uri.path,
        // `?upgrade=1` = 用户**主动**来换身份（游客转正、或收据冲突时换账号）。
        // 没有它就说明这次是守卫自己把人弹过来的，那就该弹回去。
        upgrading: state.uri.queryParameters[kUpgradeParam] == '1',
      );
    },
    refreshListenable: _GoRouterRefreshStream(ref),
    routes: [
      // 登录页（全屏）
      GoRoute(
        path: '/login',
        name: 'login',
        // 解析 URL 是路由的活，页面只收一个布尔值（见 LoginPage.upgrading）
        builder: (context, state) => LoginPage(
          upgrading: state.uri.queryParameters[kUpgradeParam] == '1',
        ),
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

      // 升级 / 权益页。恢复购买已改为进页面时按"有没有票"自动静默执行,
      // 不再由入口带参数决定(旧的 `?restore=1` 已无生产者)。
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
