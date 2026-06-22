// lib/features/content/data/models/object_list_model.dart
import 'package:equatable/equatable.dart';

/// 对象内容状态（universal-catalog spec）。未知/缺省按 ready 处理（最不打扰）。
enum ContentStatus { stub, generating, ready, empty }

ContentStatus contentStatusFrom(String? s) {
  switch (s) {
    case 'stub':
      return ContentStatus.stub;
    case 'generating':
      return ContentStatus.generating;
    case 'empty':
      return ContentStatus.empty;
    case 'ready':
    default:
      return ContentStatus.ready;
  }
}

class ObjectListItem extends Equatable {
  const ObjectListItem({
    required this.qid,
    required this.title,
    required this.artist,
    required this.year,
    required this.thumbnail,
    required this.status,
  });

  final String qid;
  final String title;
  final String artist;
  final String? year;
  final String? thumbnail;
  final ContentStatus status;

  bool get isStub => status == ContentStatus.stub;

  factory ObjectListItem.fromJson(Map<String, dynamic> j) => ObjectListItem(
        qid: j['qid'] as String? ?? '',
        title: j['title'] as String? ?? '未命名',
        artist: j['artist'] as String? ?? '',
        year: j['year'] as String?,
        thumbnail: j['thumbnail'] as String?,
        status: contentStatusFrom(j['content_status'] as String?),
      );

  @override
  List<Object?> get props => [qid, title, artist, year, thumbnail, status];
}

class ObjectListPage extends Equatable {
  const ObjectListPage({
    required this.items,
    required this.total,
    required this.limit,
    required this.offset,
  });

  final List<ObjectListItem> items;
  final int total;
  final int limit;
  final int offset;

  bool get hasMore => offset + items.length < total;

  factory ObjectListPage.fromJson(Map<String, dynamic> j) => ObjectListPage(
        items: (j['items'] as List?)
                ?.whereType<Map<String, dynamic>>()
                .map(ObjectListItem.fromJson)
                .toList() ??
            const [],
        total: (j['total'] as num?)?.toInt() ?? 0,
        limit: (j['limit'] as num?)?.toInt() ?? 50,
        offset: (j['offset'] as num?)?.toInt() ?? 0,
      );

  @override
  List<Object?> get props => [items, total, limit, offset];
}
