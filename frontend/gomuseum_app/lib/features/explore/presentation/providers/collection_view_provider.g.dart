// GENERATED CODE - DO NOT MODIFY BY HAND

part of 'collection_view_provider.dart';

// **************************************************************************
// RiverpodGenerator
// **************************************************************************

String _$collectionGridViewHash() =>
    r'01497b47dc02ae90736dd12fa2c3abb2df649526';

/// 馆藏目录用大图网格(true)还是列表(false)。
///
/// **默认大图**(用户 2026-10-03 定):在馆里的人是「看见一幅画回 App 找它」,
/// 记得的是画面不是标题。选择存本机,跨馆通用;与 [AutoSavePhoto] 同模式。
///
/// Copied from [CollectionGridView].
@ProviderFor(CollectionGridView)
final collectionGridViewProvider =
    NotifierProvider<CollectionGridView, bool>.internal(
  CollectionGridView.new,
  name: r'collectionGridViewProvider',
  debugGetCreateSourceHash: const bool.fromEnvironment('dart.vm.product')
      ? null
      : _$collectionGridViewHash,
  dependencies: null,
  allTransitiveDependencies: null,
);

typedef _$CollectionGridView = Notifier<bool>;
// ignore_for_file: type=lint
// ignore_for_file: subtype_of_sealed_class, invalid_use_of_internal_member, invalid_use_of_visible_for_testing_member, deprecated_member_use_from_same_package
