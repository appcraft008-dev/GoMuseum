/// 最近搜索:只存本机(SharedPreferences),不上传、不跟账号走。
///
/// 范围 [scope] = 'global'(探索页)或馆 slug(馆内搜索),各记各的。
/// 只在用户点开结果/按回车时记一条(边打字边搜,记每次输入会留下"圣安""圣安东"这类碎片)。
library;

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:shared_preferences/shared_preferences.dart';

const kRecentSearchMax = 5;

final recentSearchesProvider =
    StateNotifierProvider.family<RecentSearches, List<String>, String>(
        (ref, scope) => RecentSearches(scope));

class RecentSearches extends StateNotifier<List<String>> {
  RecentSearches(this.scope) : super(const []) {
    _loaded = _load();
  }

  final String scope;
  late final Future<void> _loaded;

  String get _key => 'recent_searches_$scope';

  Future<void> _load() async {
    final sp = await SharedPreferences.getInstance();
    if (mounted) state = sp.getStringList(_key) ?? const [];
  }

  /// 记一条:新的在前;同一个词(不分大小写)挪到最前不重复;最多 [kRecentSearchMax] 条。
  Future<void> add(String q) async {
    q = q.trim();
    if (q.isEmpty) return;
    await _loaded; // 防止加载结果晚到、把刚记的覆盖掉
    final lower = q.toLowerCase();
    await _save([q, ...state.where((s) => s.toLowerCase() != lower)]
        .take(kRecentSearchMax)
        .toList());
  }

  Future<void> remove(String q) async {
    await _loaded;
    await _save(state.where((s) => s != q).toList());
  }

  Future<void> clear() => _save(const []);

  Future<void> _save(List<String> v) async {
    if (mounted) state = v;
    final sp = await SharedPreferences.getInstance();
    await sp.setStringList(_key, v);
  }
}
