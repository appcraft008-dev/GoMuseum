import 'package:riverpod_annotation/riverpod_annotation.dart';
import 'package:shared_preferences/shared_preferences.dart';

part 'collection_view_provider.g.dart';

/// 馆藏目录用大图网格(true)还是列表(false)。
///
/// **默认大图**(用户 2026-10-03 定):在馆里的人是「看见一幅画回 App 找它」,
/// 记得的是画面不是标题。选择存本机,跨馆通用;与 [AutoSavePhoto] 同模式。
@Riverpod(keepAlive: true)
class CollectionGridView extends _$CollectionGridView {
  static const String _key = 'collection_grid_view';

  @override
  bool build() {
    _load();
    return true;
  }

  Future<void> _load() async {
    final prefs = await SharedPreferences.getInstance();
    state = prefs.getBool(_key) ?? true;
  }

  Future<void> toggle() async {
    state = !state;
    final prefs = await SharedPreferences.getInstance();
    await prefs.setBool(_key, state);
  }
}
