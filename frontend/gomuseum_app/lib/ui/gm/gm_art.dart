/// 设计稿艺术素材（公有领域梵高作品实拍裁切）
///
/// 与设计稿 `gm-shared.jsx` 的 GM_ART 对应，用作种子数据与占位图。
library;

class GmArtwork {
  const GmArtwork({
    required this.asset,
    required this.title,
    this.artist,
    this.year,
    this.museum,
  });

  final String asset;
  final String title;
  final String? artist;
  final String? year;
  final String? museum;
}

class GmArt {
  GmArt._();

  static const bedroom = GmArtwork(
    asset: 'assets/art/crop-bedroom.png',
    title: '在阿尔的卧室',
    artist: '文森特·梵高',
    year: '1889',
    museum: '奥赛博物馆',
  );
  static const rhone = GmArtwork(
    asset: 'assets/art/crop-rhone.png',
    title: '罗纳河上的星夜',
    artist: '文森特·梵高',
    year: '1888',
    museum: '奥赛博物馆',
  );
  static const self1889 = GmArtwork(
    asset: 'assets/art/crop-self1889.png',
    title: '自画像',
    artist: '文森特·梵高',
    year: '1889',
    museum: '奥赛博物馆',
  );
  static const plain = GmArtwork(
    asset: 'assets/art/crop-plain.png',
    title: '奥维尔平原',
    artist: '文森特·梵高',
    year: '1890',
    museum: '奥赛博物馆',
  );
  static const crows = GmArtwork(
    asset: 'assets/art/crop-crows.png',
    title: '麦田群鸦',
    artist: '文森特·梵高',
    year: '1890',
    museum: '梵高博物馆',
  );
  static const thunder = GmArtwork(
    asset: 'assets/art/crop-thunder.png',
    title: '雷雨云下的麦田',
    artist: '文森特·梵高',
    year: '1890',
    museum: '梵高博物馆',
  );
  static const self1887 = GmArtwork(
    asset: 'assets/art/crop-self1887.png',
    title: '自画像',
    artist: '文森特·梵高',
    year: '1887',
    museum: '荷兰国家博物馆',
  );
  static const orsayHall = GmArtwork(
    asset: 'assets/art/orsay-hall.webp',
    title: '奥赛博物馆',
  );
}
