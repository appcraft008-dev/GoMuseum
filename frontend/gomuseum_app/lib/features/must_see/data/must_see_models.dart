// lib/features/must_see/data/must_see_models.dart
// GET /api/v1/museums/{slug}/must-see → 必看护照页(spec 2026-10-27 必看打卡 §五.4)。
//
// ⚠️ 整条解析不许裸强转:类型不对就当"没有",绝不让护照页因一个字段崩掉。

/// 必看件在馆内的位置(官网取得到才有)。三段都可能缺。
class MustSeeLocation {
  const MustSeeLocation({this.wing, this.level, this.room});

  final String? wing;
  final int? level;
  final String? room;

  /// 三段都没有(或类型都不对)→ null。
  static MustSeeLocation? fromJson(dynamic raw) {
    if (raw is! Map) return null;
    final wing = raw['wing'] is String ? raw['wing'] as String : null;
    final level = raw['level'] is int ? raw['level'] as int : null;
    final room = raw['room'] is String ? raw['room'] as String : null;
    if (wing == null && level == null && room == null) return null;
    return MustSeeLocation(wing: wing, level: level, room: room);
  }
}

class MustSeeItem {
  const MustSeeItem({
    required this.qid,
    required this.title,
    required this.artist,
    this.thumbnail,
    this.location,
  });

  final String qid;
  final String title;
  final String artist;
  final String? thumbnail;
  final MustSeeLocation? location;
}

class MustSeeMedal {
  const MustSeeMedal({required this.completedAt, required this.count});

  final DateTime completedAt;
  final int count;
}

class MustSeeData {
  const MustSeeData({
    required this.items,
    required this.checked,
    required this.roundStartedAt,
    required this.completed,
    required this.medals,
  });

  final List<MustSeeItem> items;

  /// 当前轮已打卡的 qid → 打卡时间(本地时区)。
  final Map<String, DateTime> checked;

  /// 当前轮开始时间;没有进行中的轮 → null(新护照)。
  final DateTime? roundStartedAt;
  final bool completed;

  /// 新的在前。
  final List<MustSeeMedal> medals;

  int get checkedCount => items.where((i) => checked.containsKey(i.qid)).length;

  factory MustSeeData.fromJson(Map<String, dynamic> j) {
    final items = <MustSeeItem>[];
    for (final raw in (j['items'] is List ? j['items'] as List : const [])) {
      if (raw is! Map || raw['qid'] is! String) continue;
      final qid = raw['qid'] as String;
      final title = raw['title'];
      items.add(MustSeeItem(
        qid: qid,
        title: title is String && title.isNotEmpty ? title : qid,
        artist: raw['artist'] is String ? raw['artist'] as String : '',
        thumbnail: raw['thumbnail'] is String &&
                (raw['thumbnail'] as String).isNotEmpty
            ? raw['thumbnail'] as String
            : null,
        location: MustSeeLocation.fromJson(raw['location']),
      ));
    }
    final checked = <String, DateTime>{};
    final rawChecked = j['checked'];
    if (rawChecked is Map) {
      for (final e in rawChecked.entries) {
        final at = _time(e.value);
        if (at != null) checked['${e.key}'] = at;
      }
    }
    final medals = <MustSeeMedal>[];
    for (final raw in (j['medals'] is List ? j['medals'] as List : const [])) {
      if (raw is! Map) continue;
      final at = _time(raw['completed_at']);
      if (at == null) continue;
      medals.add(MustSeeMedal(
          completedAt: at,
          count: raw['count'] is int ? raw['count'] as int : 0));
    }
    return MustSeeData(
      items: items,
      checked: checked,
      roundStartedAt: _time(j['round_started_at']),
      completed: j['completed'] == true,
      medals: medals,
    );
  }

  /// 后端发带时区的 UTC 串(+00:00);一律转本地,日期签按用户所在地显示。
  static DateTime? _time(dynamic raw) =>
      raw is String ? DateTime.tryParse(raw)?.toLocal() : null;
}
