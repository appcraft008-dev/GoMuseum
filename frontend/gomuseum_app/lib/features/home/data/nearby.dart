/// 「当前在哪座城市」(spec 2026-09-29-home-nearby-explore-by-city §一)。
///
/// 优先级:手机粗略定位 > 12 小时内的**现场拍照**命中 > 无。全部只在手机本地判,
/// 用户位置**不上传**。
///
/// ⚠️ 图库上传的识别**不算**(用户原话:可能在家翻旧照、出发前拿网图试)。
/// 同理不算:探索页浏览了哪家馆、照片 EXIF 里的 GPS(那是"拍时在哪"不是"现在在哪")。
library;

import 'dart:math' as math;

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:geolocator/geolocator.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'package:gomuseum_app/features/content/data/models/museum_summary_model.dart';
import 'package:gomuseum_app/features/content/presentation/providers/catalog_providers.dart';

/// 现场拍照命中多久内算"人还在那座城市":一个参观日。
const kLiveMatchWindow = Duration(hours: 12);

/// 「附近」的半径。一座城市的馆通常在 10 km 内;50 km 覆盖到郊区的馆(凡尔赛等)。
const kNearbyKm = 50.0;

enum NearbyMode {
  /// 手机定位:50 km 内的馆,按距离排
  gps,

  /// 12 小时内现场拍照命中的那家馆所在城市
  live,

  /// 不知道在哪:不冒充「附近」
  none,
}

class Nearby {
  const Nearby(this.mode, this.museums, {this.cityKey});

  final NearbyMode mode;

  /// 首页 01 要列的馆(gps/live 时只含当前城市;none 时是全部)。
  final List<MuseumSummary> museums;

  /// 当前城市的去重键(中文城市名,与探索页同一口径);none 时为 null。
  final String? cityKey;
}

/// 最后一次**现场拍照**命中:哪家馆、什么时候。
class LiveMatch {
  const LiveMatch(this.slug, this.at);

  final String slug;
  final DateTime at;
}

/// 两点球面距离(km,haversine)。
double distanceKm(double lat1, double lng1, double lat2, double lng2) {
  const r = 6371.0;
  double rad(double d) => d * math.pi / 180;
  final dLat = rad(lat2 - lat1), dLng = rad(lng2 - lng1);
  final a = math.pow(math.sin(dLat / 2), 2) +
      math.cos(rad(lat1)) *
          math.cos(rad(lat2)) *
          math.pow(math.sin(dLng / 2), 2);
  return 2 * r * math.asin(math.sqrt(a));
}

/// 纯函数:按优先级判当前城市。可测,不碰插件与存储。
Nearby resolveNearby(
  List<MuseumSummary> all, {
  ({double lat, double lng})? here,
  LiveMatch? live,
  required DateTime now,
}) {
  if (here != null) {
    final withDist = <(MuseumSummary, double)>[
      for (final m in all)
        // 后端 `coordinates` [lat, lng];缺(老后端/yaml 没配)→ 空表,不参与距离排序
        if (m.coordinates.length == 2)
          (
            m,
            distanceKm(here.lat, here.lng, m.coordinates[0], m.coordinates[1])
          ),
    ]..sort((a, b) => a.$2.compareTo(b.$2));
    final near = withDist.where((e) => e.$2 <= kNearbyKm).toList();
    // 定位到了、但身边没有我们的馆 → 不冒充附近,往下看现场命中
    if (near.isNotEmpty) {
      return Nearby(NearbyMode.gps, [for (final e in near) e.$1],
          cityKey: near.first.$1.city);
    }
  }
  if (live != null && now.difference(live.at) <= kLiveMatchWindow) {
    final hit = all.where((m) => m.slug == live.slug).firstOrNull;
    if (hit != null) {
      return Nearby(
          NearbyMode.live, all.where((m) => m.city == hit.city).toList(),
          cityKey: hit.city);
    }
  }
  return Nearby(NearbyMode.none, all);
}

// ── 现场命中的本地存储(只存手机上,不上传)──

const _kSlug = 'live_match_slug';
const _kAt = 'live_match_at';

/// 记一次现场命中。**只在快门拍照 + 命中时调用**(见 camera_page)。
Future<void> recordLiveMatch(String slug, {DateTime? at}) async {
  final p = await SharedPreferences.getInstance();
  await p.setString(_kSlug, slug);
  await p.setString(_kAt, (at ?? DateTime.now()).toUtc().toIso8601String());
}

Future<LiveMatch?> readLiveMatch() async {
  try {
    final p = await SharedPreferences.getInstance();
    final slug = p.getString(_kSlug);
    final at = DateTime.tryParse(p.getString(_kAt) ?? '');
    if (slug == null || at == null) return null;
    return LiveMatch(slug, at.toLocal());
  } catch (_) {
    return null;
  }
}

// ── 手机定位:只**读**已有授权,不在这里弹权限(见 requestLocation)──

final deviceLocationProvider =
    FutureProvider.autoDispose<({double lat, double lng})?>((ref) async {
  try {
    final perm = await Geolocator.checkPermission();
    if (perm != LocationPermission.whileInUse &&
        perm != LocationPermission.always) {
      return null;
    }
    final pos = await Geolocator.getLastKnownPosition() ??
        await Geolocator.getCurrentPosition(
          locationSettings: const LocationSettings(
            accuracy: LocationAccuracy.low,
            timeLimit: Duration(seconds: 6),
          ),
        );
    return (lat: pos.latitude, lng: pos.longitude);
  } catch (_) {
    // 没开定位服务/超时/桌面测试环境:当作不知道,不能把首页打死
    return null;
  }
});

/// 用户点了「开启定位」才请求权限 —— 不在启动时弹。
Future<void> requestLocation(WidgetRef ref) async {
  try {
    await Geolocator.requestPermission();
  } catch (_) {}
  ref.invalidate(deviceLocationProvider);
}

final nearbyProvider = FutureProvider.autoDispose<Nearby>((ref) async {
  final all = await ref.watch(museumsListProvider.future);
  final here = await ref.watch(deviceLocationProvider.future);
  final live = await readLiveMatch();
  return resolveNearby(all, here: here, live: live, now: DateTime.now());
});
