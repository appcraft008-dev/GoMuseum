# Payment Module (支付模块)

完整的支付模块实现，遵循Clean Architecture模式，集成了应用内购买(IAP)和后端权益验证。

## 模块结构

```
payment/
├── domain/                    # 领域层（业务逻辑）
│   ├── entities/             # 实体
│   │   ├── user_benefits.dart          # 用户权益实体
│   │   ├── purchase_result.dart        # 购买结果实体
│   │   └── consumption_result.dart     # 配额消耗结果实体
│   ├── repositories/         # 仓储接口
│   │   └── payment_repository.dart
│   └── usecases/            # 用例
│       ├── verify_purchase.dart        # 验证购买
│       ├── get_user_benefits.dart      # 获取用户权益
│       └── consume_recognition.dart    # 消耗识别配额
├── data/                      # 数据层
│   ├── models/               # 数据模型（带JSON序列化）
│   │   ├── user_benefits_model.dart
│   │   ├── purchase_result_model.dart
│   │   └── consumption_result_model.dart
│   ├── datasources/          # 数据源
│   │   └── payment_remote_datasource.dart
│   └── repositories/         # 仓储实现
│       └── payment_repository_impl.dart
└── presentation/             # 表现层
    ├── providers/           # Riverpod状态管理
    │   ├── payment_providers.dart      # 基础Provider
    │   └── benefits_provider.dart      # 权益状态Provider
    ├── pages/               # 页面
    │   └── benefits_page.dart          # 权益与购买页面
    └── widgets/             # 组件
        ├── product_card.dart           # 商品卡片
        └── benefits_status_widget.dart # 权益状态组件
```

## 功能特性

### 1. 用户权益管理

- 自动获取和刷新用户权益
- 支持匿名用户（基于设备ID）
- 实时更新权益状态

### 2. IAP购买流程

- iOS/Android应用内购买
- 购买凭证后端验证
- 自动应用权益

### 3. 配额消耗

- 识别前检查权限
- 消耗识别次数
- 实时更新剩余配额

## 商品定义

项目支持三种商品类型：

```dart
// 10次识别包（消耗型商品）
com.gomuseum.recognition_pack_10 - €1.99

// 日卡（消耗型商品，24小时无限识别）
com.gomuseum.day_pass - €2.99

// 年度会员（订阅型商品，一年无限识别）
com.gomuseum.premium_annual - €19.9
```

## 使用方法

### 1. 导航到权益页面

```dart
import 'package:gomuseum_app/features/payment/presentation/pages/benefits_page.dart';

// 在路由中导航
Navigator.push(
  context,
  MaterialPageRoute(builder: (context) => const BenefitsPage()),
);
```

### 2. 获取用户权益状态

```dart
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:gomuseum_app/features/payment/presentation/providers/benefits_provider.dart';

class MyWidget extends ConsumerWidget {
  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final benefitsAsync = ref.watch(benefitsStateProvider);

    return benefitsAsync.when(
      data: (benefits) {
        // 检查是否有识别权限
        if (benefits.hasAccess) {
          // 用户有权限
          return Text('剩余识别次数: ${benefits.recognitionQuota}');
        } else {
          // 提示用户购买
          return ElevatedButton(
            onPressed: () => _navigateToBenefitsPage(context),
            child: Text('购买识别包'),
          );
        }
      },
      loading: () => CircularProgressIndicator(),
      error: (error, _) => Text('加载失败: $error'),
    );
  }
}
```

### 3. 在识别前检查和消耗配额

```dart
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:gomuseum_app/features/payment/presentation/providers/benefits_provider.dart';

class RecognitionWidget extends ConsumerWidget {
  Future<void> _performRecognition(WidgetRef ref) async {
    final benefitsNotifier = ref.read(benefitsStateProvider.notifier);

    // 检查是否有识别权限
    if (!benefitsNotifier.hasRecognitionAccess) {
      // 提示用户购买
      _showPurchaseDialog();
      return;
    }

    // 消耗配额（仅对识别包用户）
    final consumed = await benefitsNotifier.consumeQuota();

    if (consumed) {
      // 执行识别
      await _doRecognition();
    } else {
      // 配额不足
      _showInsufficientQuotaDialog();
    }
  }

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    return ElevatedButton(
      onPressed: () => _performRecognition(ref),
      child: Text('识别艺术品'),
    );
  }
}
```

### 4. 使用权益状态Widget

```dart
import 'package:gomuseum_app/features/payment/presentation/widgets/benefits_status_widget.dart';

class SettingsPage extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: Text('设置')),
      body: ListView(
        children: [
          // 显示权益状态
          BenefitsStatusWidget(),
          // 其他设置选项...
        ],
      ),
    );
  }
}
```

## 后端API集成

模块已配置为与后端API通信：

### 1. 验证购买

```
POST /api/v1/payment/verify
{
  "platform": "ios" | "android",
  "receipt_data": "...",
  "product_id": "com.gomuseum.recognition_pack_10",
  "user_id": "optional_user_id",
  "device_id": "device_unique_id"
}
```

### 2. 获取权益

```
GET /api/v1/payment/benefits?device_id=xxx&user_id=xxx
```

### 3. 消耗配额

```
POST /api/v1/payment/consume?device_id=xxx&user_id=xxx
```

## 配置要求

### 1. pubspec.yaml 依赖

```yaml
dependencies:
  in_app_purchase: ^3.1.11
  device_info_plus: ^10.1.0
  flutter_riverpod: ^2.4.0
  riverpod_annotation: ^2.3.0
  dio: ^5.4.0
  dartz: ^0.10.1
```

### 2. iOS配置

在 `ios/Runner/Info.plist` 中添加：

```xml
<key>SKPaymentTransactionObserver</key>
<true/>
```

### 3. Android配置

在 `android/app/src/main/AndroidManifest.xml` 中添加：

```xml
<uses-permission android:name="com.android.vending.BILLING" />
```

## 状态管理

使用 Riverpod 进行状态管理：

- `benefitsStateProvider`: 自动加载和管理用户权益状态
- `deviceIdProvider`: 自动获取设备ID
- `paymentRepositoryProvider`: 提供支付仓储实例
- 所有UseCase都有对应的Provider

## 错误处理

模块使用 Either<Failure, Success> 模式处理错误：

```dart
final result = await ref.read(getUserBenefitsUseCaseProvider)(
  deviceId: deviceId,
  userId: userId,
);

result.fold(
  (failure) {
    // 处理错误
    if (failure is NetworkFailure) {
      showSnackBar('网络连接失败');
    } else if (failure is ServerFailure) {
      showSnackBar('服务器错误: ${failure.message}');
    }
  },
  (benefits) {
    // 处理成功
    print('用户有 ${benefits.recognitionQuota} 次识别配额');
  },
);
```

## 测试

建议为以下部分编写测试：

1. **Domain层测试**
   - Entity equality tests
   - UseCase logic tests

2. **Data层测试**
   - Model JSON serialization tests
   - Repository implementation tests
   - Remote datasource tests

3. **Presentation层测试**
   - Widget tests
   - Provider state management tests

## 注意事项

1. **匿名用户支持**: 目前使用 `device_id` 支持匿名用户，`user_id` 为可选参数
2. **设备ID**: 使用 `device_info_plus` 获取唯一设备标识
3. **购买验证**: 所有IAP购买都需要后端验证
4. **权益同步**: 权益状态保存在后端，支持多设备同步（使用user_id时）
5. **网络要求**: 所有操作都需要网络连接

## 后续优化建议

1. 添加本地缓存权益状态（减少API调用）
2. 支持用户账号系统集成
3. 添加购买历史记录
4. 实现购买恢复功能
5. 添加促销活动支持
6. 实现订阅自动续费通知

## 相关文档

- [in_app_purchase package](https://pub.dev/packages/in_app_purchase)
- [device_info_plus package](https://pub.dev/packages/device_info_plus)
- [Riverpod documentation](https://riverpod.dev)
- [Clean Architecture](https://blog.cleancoder.com/uncle-bob/2012/08/13/the-clean-architecture.html)
