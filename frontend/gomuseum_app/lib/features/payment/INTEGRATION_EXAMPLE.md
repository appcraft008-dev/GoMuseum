# Payment Module Integration Example

# 支付模块集成示例

本文档展示如何将支付模块集成到现有的识别(Recognition)流程中。

## 场景1: 在识别前检查权益

### 修改识别页面，添加权益检查

```dart
// lib/features/recognition/presentation/pages/recognition_page.dart

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:image_picker/image_picker.dart';
import '../../../payment/presentation/providers/benefits_provider.dart';
import '../../../payment/presentation/pages/benefits_page.dart';

class RecognitionPage extends ConsumerStatefulWidget {
  const RecognitionPage({super.key});

  @override
  ConsumerState<RecognitionPage> createState() => _RecognitionPageState();
}

class _RecognitionPageState extends ConsumerState<RecognitionPage> {
  final ImagePicker _picker = ImagePicker();

  /// 选择并识别图片
  Future<void> _pickAndRecognizeImage(ImageSource source) async {
    // 1. 检查用户权益
    final benefitsNotifier = ref.read(benefitsStateProvider.notifier);

    if (!benefitsNotifier.hasRecognitionAccess) {
      // 用户没有权限，显示购买对话框
      _showPurchaseDialog();
      return;
    }

    // 2. 选择图片
    final XFile? image = await _picker.pickImage(source: source);
    if (image == null) return;

    // 3. 消耗配额（仅对付费次数包用户）
    final benefits = ref.read(benefitsStateProvider).value;
    if (benefits != null &&
        !benefits.isPremium &&
        !benefits.dayPassActive &&
        benefits.recognitionQuota > 0) {

      final consumed = await benefitsNotifier.consumeQuota();
      if (!consumed) {
        _showQuotaConsumeFailedDialog();
        return;
      }
    }

    // 4. 执行识别
    await _performRecognition(image);
  }

  /// 显示购买对话框
  void _showPurchaseDialog() {
    showDialog(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('需要购买识别包'),
        content: const Text('您的识别次数已用完，请购买识别包、日卡或开通会员以继续使用。'),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context),
            child: const Text('取消'),
          ),
          ElevatedButton(
            onPressed: () {
              Navigator.pop(context);
              Navigator.push(
                context,
                MaterialPageRoute(builder: (_) => const BenefitsPage()),
              );
            },
            child: const Text('去购买'),
          ),
        ],
      ),
    );
  }

  /// 显示配额消耗失败对话框
  void _showQuotaConsumeFailedDialog() {
    ScaffoldMessenger.of(context).showSnackBar(
      const SnackBar(
        content: Text('识别配额扣除失败，请稍后重试'),
        backgroundColor: Colors.red,
      ),
    );
  }

  /// 执行识别
  Future<void> _performRecognition(XFile image) async {
    // 原有的识别逻辑
    // ...
  }

  @override
  Widget build(BuildContext context) {
    // 监听权益状态
    final benefitsAsync = ref.watch(benefitsStateProvider);

    return Scaffold(
      appBar: AppBar(
        title: const Text('艺术品识别'),
        actions: [
          // 显示剩余次数或会员状态
          benefitsAsync.when(
            data: (benefits) {
              if (benefits.isPremium) {
                return const Padding(
                  padding: EdgeInsets.all(16),
                  child: Row(
                    children: [
                      Icon(Icons.star, color: Colors.amber),
                      SizedBox(width: 4),
                      Text('会员'),
                    ],
                  ),
                );
              } else if (benefits.dayPassActive) {
                return const Padding(
                  padding: EdgeInsets.all(16),
                  child: Row(
                    children: [
                      Icon(Icons.today, color: Colors.blue),
                      SizedBox(width: 4),
                      Text('日卡'),
                    ],
                  ),
                );
              } else {
                return Padding(
                  padding: const EdgeInsets.all(16),
                  child: Text('剩余: ${benefits.recognitionQuota}次'),
                );
              }
            },
            loading: () => const SizedBox(),
            error: (_, __) => const SizedBox(),
          ),
          // 导航到权益页面
          IconButton(
            icon: const Icon(Icons.card_membership),
            onPressed: () => Navigator.push(
              context,
              MaterialPageRoute(builder: (_) => const BenefitsPage()),
            ),
          ),
        ],
      ),
      body: Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            ElevatedButton.icon(
              onPressed: () => _pickAndRecognizeImage(ImageSource.camera),
              icon: const Icon(Icons.camera_alt),
              label: const Text('拍照识别'),
            ),
            const SizedBox(height: 16),
            ElevatedButton.icon(
              onPressed: () => _pickAndRecognizeImage(ImageSource.gallery),
              icon: const Icon(Icons.photo_library),
              label: const Text('从相册选择'),
            ),
          ],
        ),
      ),
    );
  }
}
```

## 场景2: 在设置页面显示权益状态

```dart
// lib/features/settings/presentation/pages/settings_page.dart

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../../payment/presentation/widgets/benefits_status_widget.dart';
import '../../../payment/presentation/pages/benefits_page.dart';

class SettingsPage extends ConsumerWidget {
  const SettingsPage({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('设置'),
      ),
      body: ListView(
        children: [
          // 权益状态卡片（可点击进入详情页）
          InkWell(
            onTap: () => Navigator.push(
              context,
              MaterialPageRoute(builder: (_) => const BenefitsPage()),
            ),
            child: const BenefitsStatusWidget(),
          ),

          // 其他设置选项
          ListTile(
            leading: const Icon(Icons.language),
            title: const Text('语言设置'),
            onTap: () {
              // 语言设置逻辑
            },
          ),

          ListTile(
            leading: const Icon(Icons.notifications),
            title: const Text('通知设置'),
            onTap: () {
              // 通知设置逻辑
            },
          ),

          const Divider(),

          ListTile(
            leading: const Icon(Icons.shopping_bag),
            title: const Text('购买记录'),
            onTap: () => Navigator.push(
              context,
              MaterialPageRoute(builder: (_) => const BenefitsPage()),
            ),
          ),

          ListTile(
            leading: const Icon(Icons.restore),
            title: const Text('恢复购买'),
            onTap: () => _restorePurchases(context),
          ),
        ],
      ),
    );
  }

  Future<void> _restorePurchases(BuildContext context) async {
    // 显示加载
    showDialog(
      context: context,
      barrierDismissible: false,
      builder: (_) => const Center(child: CircularProgressIndicator()),
    );

    // TODO: 调用IAP服务恢复购买
    await Future.delayed(const Duration(seconds: 2));

    if (context.mounted) {
      Navigator.pop(context);
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('购买恢复完成')),
      );
    }
  }
}
```

## 场景3: 在主页显示权益提示

```dart
// lib/features/home/presentation/pages/home_page.dart

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../../payment/presentation/providers/benefits_provider.dart';
import '../../../payment/presentation/pages/benefits_page.dart';

class HomePage extends ConsumerWidget {
  const HomePage({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final benefitsAsync = ref.watch(benefitsStateProvider);

    return Scaffold(
      appBar: AppBar(
        title: const Text('GoMuseum'),
      ),
      body: Column(
        children: [
          // 权益提示横幅（仅在需要时显示）
          benefitsAsync.when(
            data: (benefits) {
              if (!benefits.hasAccess) {
                return _buildPromoBanner(
                  context,
                  '开启您的艺术探索之旅',
                  '立即购买识别包或开通会员',
                  Colors.blue,
                  Icons.star,
                );
              } else if (benefits.recognitionQuota > 0 &&
                         benefits.recognitionQuota <= 3) {
                return _buildPromoBanner(
                  context,
                  '识别次数即将用完',
                  '剩余 ${benefits.recognitionQuota} 次，点击购买更多',
                  Colors.orange,
                  Icons.warning,
                );
              }
              return const SizedBox.shrink();
            },
            loading: () => const SizedBox.shrink(),
            error: (_, __) => const SizedBox.shrink(),
          ),

          // 主页内容
          Expanded(
            child: Center(
              child: Text('欢迎使用 GoMuseum'),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildPromoBanner(
    BuildContext context,
    String title,
    String subtitle,
    Color color,
    IconData icon,
  ) {
    return Container(
      margin: const EdgeInsets.all(16),
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: color.withOpacity(0.1),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: color.withOpacity(0.3)),
      ),
      child: InkWell(
        onTap: () => Navigator.push(
          context,
          MaterialPageRoute(builder: (_) => const BenefitsPage()),
        ),
        child: Row(
          children: [
            Icon(icon, color: color, size: 40),
            const SizedBox(width: 16),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    title,
                    style: TextStyle(
                      fontSize: 16,
                      fontWeight: FontWeight.bold,
                      color: color,
                    ),
                  ),
                  const SizedBox(height: 4),
                  Text(
                    subtitle,
                    style: TextStyle(
                      fontSize: 14,
                      color: color.withOpacity(0.8),
                    ),
                  ),
                ],
              ),
            ),
            Icon(Icons.arrow_forward_ios, color: color, size: 16),
          ],
        ),
      ),
    );
  }
}
```

## 场景4: UseCase层集成（可选的更深层集成）

如果您想在UseCase层面就控制权益检查，可以创建一个包装的UseCase：

```dart
// lib/features/recognition/domain/usecases/recognize_with_quota_check.dart

import 'package:cross_file/cross_file.dart';
import 'package:dartz/dartz.dart';
import '../../../../core/error/failures.dart';
import '../../../payment/domain/usecases/consume_recognition.dart';
import '../../../payment/domain/usecases/get_user_benefits.dart';
import '../entities/recognition_result.dart';
import './recognize_artwork.dart';

/// 带权益检查的识别UseCase
class RecognizeWithQuotaCheck {
  final RecognizeArtwork recognizeArtwork;
  final GetUserBenefits getUserBenefits;
  final ConsumeRecognition consumeRecognition;

  const RecognizeWithQuotaCheck({
    required this.recognizeArtwork,
    required this.getUserBenefits,
    required this.consumeRecognition,
  });

  Future<Either<Failure, RecognitionResult>> call({
    required XFile imageFile,
    required String deviceId,
    String? userId,
  }) async {
    // 1. 检查用户权益
    final benefitsResult = await getUserBenefits(
      deviceId: deviceId,
      userId: userId,
    );

    return benefitsResult.fold(
      (failure) => Left(failure),
      (benefits) async {
        // 2. 验证是否有权限
        if (!benefits.hasAccess) {
          return const Left(ValidationFailure(
            'No recognition access. Please purchase recognition pack or membership.',
          ));
        }

        // 3. 如果是次数包用户，先消耗配额
        if (!benefits.isPremium &&
            !benefits.dayPassActive &&
            benefits.recognitionQuota > 0) {

          final consumeResult = await consumeRecognition(
            deviceId: deviceId,
            userId: userId,
          );

          final consumeSuccess = consumeResult.fold(
            (failure) => false,
            (result) => result.success,
          );

          if (!consumeSuccess) {
            return const Left(ServerFailure('Failed to consume recognition quota'));
          }
        }

        // 4. 执行识别
        return await recognizeArtwork(imageFile);
      },
    );
  }
}
```

然后在Provider中注册：

```dart
// lib/features/recognition/presentation/providers/recognition_providers.dart

@riverpod
RecognizeWithQuotaCheck recognizeWithQuotaCheckUseCase(
  RecognizeWithQuotaCheckUseCaseRef ref,
) {
  return RecognizeWithQuotaCheck(
    recognizeArtwork: ref.watch(recognizeArtworkUseCaseProvider),
    getUserBenefits: ref.watch(getUserBenefitsUseCaseProvider),
    consumeRecognition: ref.watch(consumeRecognitionUseCaseProvider),
  );
}
```

## 路由集成

在主路由配置中添加支付相关页面：

```dart
// lib/core/router/app_router.dart

import 'package:go_router/go_router.dart';
import '../../features/payment/presentation/pages/benefits_page.dart';

final appRouter = GoRouter(
  routes: [
    GoRoute(
      path: '/',
      builder: (context, state) => const HomePage(),
    ),
    GoRoute(
      path: '/recognition',
      builder: (context, state) => const RecognitionPage(),
    ),
    GoRoute(
      path: '/benefits',
      builder: (context, state) => const BenefitsPage(),
    ),
    GoRoute(
      path: '/settings',
      builder: (context, state) => const SettingsPage(),
    ),
  ],
);
```

## 初始化流程

在app启动时初始化IAP和加载权益：

```dart
// lib/main.dart

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'features/payment/presentation/providers/benefits_provider.dart';

void main() async {
  WidgetsFlutterBinding.ensureInitialized();

  runApp(
    const ProviderScope(
      child: MyApp(),
    ),
  );
}

class MyApp extends ConsumerStatefulWidget {
  const MyApp({super.key});

  @override
  ConsumerState<MyApp> createState() => _MyAppState();
}

class _MyAppState extends ConsumerState<MyApp> {
  @override
  void initState() {
    super.initState();
    // 预加载用户权益
    Future.microtask(() {
      ref.read(benefitsStateProvider);
    });
  }

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'GoMuseum',
      theme: ThemeData(
        primarySwatch: Colors.blue,
      ),
      home: const HomePage(),
    );
  }
}
```

## 注意事项

1. **错误处理**: 始终处理网络错误和支付失败的情况
2. **用户体验**: 在权益即将用完时提前提醒用户
3. **本地缓存**: 考虑缓存权益状态以减少API调用
4. **测试**: 在真实设备上测试IAP流程（模拟器不支持真实购买）
5. **权益刷新**: 在关键操作前刷新权益状态确保数据准确

## 常见问题

**Q: 购买后权益没有立即更新？**
A: 调用 `ref.read(benefitsStateProvider.notifier).refresh()` 手动刷新

**Q: 如何支持离线使用？**
A: 当前设计需要网络连接验证权益，可以添加本地缓存支持短时间离线

**Q: 如何处理购买失败？**
A: 使用 `onError` 回调处理购买错误，向用户显示友好的错误信息

**Q: 多设备同步？**
A: 使用 `user_id` 参数可以实现基于用户账号的多设备同步
