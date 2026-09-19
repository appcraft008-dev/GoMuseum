/// 足迹的分组单位：**一次参观**。
///
/// 这里只有纯逻辑，不碰 Flutter —— 分组错了整页就是错的，而它值得被直接单测，
/// 不必为了验一条分组规则去 pump 一棵带网络缩略图的 widget 树。
library;

import 'package:gomuseum_app/features/history/domain/entities/history_item.dart';

/// 一次参观 = **同一天 × 同一个馆**。
///
/// 为什么不是「按博物馆分组」：那样跨两年的三次卢浮宫会塌成一块，
/// 「什么时候去的」这一半恰好就没了 —— 而那正是用户要从足迹里读出来的东西。
/// 为什么不是「只按天分组」（改版前的行为）：巴黎奥赛和橘园走路十分钟，
/// 一天连看两个是常态，混在一块读不出"这一段是在哪儿看的"。
class FootprintVisit {
  FootprintVisit({
    required this.day,
    required this.museumSlug,
    required this.items,
  });

  /// 当天零点。**分组用的是它，不是格式化出来的日期字符串** ——
  /// 见 [groupFootprintsByVisit] 里那条跨年的纪律。
  final DateTime day;

  /// 老事件 / 老后端不带这个字段，可空。
  final String? museumSlug;

  final List<HistoryItem> items;

  /// 这次参观的时间点 = 最近的一条（列表内部也是新到旧）。
  DateTime get latest => items.first.timestamp;
}

/// 足迹 → 一次次参观，新到旧。
///
/// 🔑 **键必须是真实日期，不能是显示标签。** 改版前这里拿 `"{month}月{day}日"`
/// 当 map 的键，而全仓库的日期文案都不含年份 —— 于是 2025-09-18 和 2026-09-18
/// 同键，去年今天会被并进今年今天那一组。零真实用户时没人撞上，
/// 但"过了很长时间再回头看"正是它发作的条件。
List<FootprintVisit> groupFootprintsByVisit(List<HistoryItem> items) {
  final sorted = [...items]..sort((a, b) => b.timestamp.compareTo(a.timestamp));
  final groups = <(DateTime, String?), FootprintVisit>{};
  for (final item in sorted) {
    final t = item.timestamp;
    final day = DateTime(t.year, t.month, t.day);
    // 按键归拢而不是按"相邻游程"：一天里奥赛→橘园→奥赛这么逛完全可能，
    // 游程分组会把它切成三次参观，而用户记忆里那天只去过两个馆。
    groups
        .putIfAbsent(
          (day, item.museumSlug),
          () =>
              FootprintVisit(day: day, museumSlug: item.museumSlug, items: []),
        )
        .items
        .add(item);
  }
  // 输入已按时间倒序，Map 保留插入顺序 → 参观序列天然也是倒序。
  return groups.values.toList();
}

/// 城市这一层要不要出现。
///
/// 现在四个馆全在巴黎，恒定一组的层级只是白占一层缩进；等荷兰/西班牙的馆上线
/// 它自己就生效了。空城市（馆未知，或馆列表还没加载完）**不计入判断** ——
/// 否则「巴黎 + 未知」会被当成跨了两个城市。
bool footprintsSpanCities(Iterable<String> cityPerVisit) =>
    cityPerVisit.where((c) => c.isNotEmpty).toSet().length >= 2;
