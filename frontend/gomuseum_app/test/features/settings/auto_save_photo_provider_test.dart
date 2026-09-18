// 「自动保存照片」的偏好必须跨冷启动活着——它决定取景页每次快门要不要写相册。
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gomuseum_app/features/settings/presentation/providers/auto_save_photo_provider.dart';
import 'package:shared_preferences/shared_preferences.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  ProviderContainer container() {
    final c = ProviderContainer();
    addTearDown(c.dispose);
    return c;
  }

  // 正负成对：只测「设过就是开」的话，一个恒返回 true 的实现照样全绿。
  test('默认关——往用户相册里写东西必须是他主动选的', () async {
    SharedPreferences.setMockInitialValues({});
    final c = container();
    expect(c.read(autoSavePhotoProvider), isFalse);
    await pumpEventQueue(); // 让异步载入跑完
    expect(c.read(autoSavePhotoProvider), isFalse);
  });

  test('设开后重建容器仍是开（回归点：偏好曾只存在内存里）', () async {
    SharedPreferences.setMockInitialValues({});
    await container().read(autoSavePhotoProvider.notifier).setEnabled(true);

    // 模拟冷启动：新容器重新 build。provider 是懒的，先 read 一次才会起
    // 异步载入，再等它回来。
    final reborn = container();
    reborn.read(autoSavePhotoProvider);
    await pumpEventQueue();
    expect(reborn.read(autoSavePhotoProvider), isTrue);
  });

  test('关掉后重建容器仍是关', () async {
    SharedPreferences.setMockInitialValues({'auto_save_photo': true});
    await container().read(autoSavePhotoProvider.notifier).setEnabled(false);

    final reborn = container();
    reborn.read(autoSavePhotoProvider);
    await pumpEventQueue();
    expect(reborn.read(autoSavePhotoProvider), isFalse);
  });
}
