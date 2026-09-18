import 'package:riverpod_annotation/riverpod_annotation.dart';
import 'package:shared_preferences/shared_preferences.dart';

part 'auto_save_photo_provider.g.dart';

/// 相册里存放 App 拍摄照片的相册名（Android MediaStore 的 `RELATIVE_PATH`）。
/// 参观拍的画与日常照片分开，用户找得到。iOS 侧 photo_manager 的
/// `saveImageWithPath` 不支持指定相册，会落在「最近项目」——两端行为不一致但都能用。
const String kAutoSaveRelativePath = 'Pictures/GoMuseum';

/// 偏好的持久化键。**取景页保存时直接读 SharedPreferences，不读下面这个
/// provider** —— provider 的值是异步载入的，冷启动后第一次 `ref.read` 拿到的
/// 还是默认值 false，那一张照片就静默丢了。这里才是真相源，provider 只是
/// 设置页开关的 UI 镜像。
const String kAutoSavePhotoKey = 'auto_save_photo';

/// 拍完是否自动把照片存进系统相册。
///
/// **默认关**：往用户自己的相册里写东西必须是他主动选的。
/// 与 [Language] 同模式：初值先给默认，再异步从 SharedPreferences 载入
/// （冷启动后极短暂为 false，设置页首帧可能显示成关，可接受）。
///
/// `keepAlive`：离开设置页就销毁的话，每次回来都要重跑一遍异步载入、期间显示
/// 成关。这是个 App 生命期的偏好，不该跟着页面来回销毁。
@Riverpod(keepAlive: true)
class AutoSavePhoto extends _$AutoSavePhoto {
  static const String _key = kAutoSavePhotoKey;

  @override
  bool build() {
    _load();
    return false;
  }

  Future<void> _load() async {
    final prefs = await SharedPreferences.getInstance();
    state = prefs.getBool(_key) ?? false;
  }

  Future<void> setEnabled(bool enabled) async {
    state = enabled;
    final prefs = await SharedPreferences.getInstance();
    await prefs.setBool(_key, enabled);
  }
}
