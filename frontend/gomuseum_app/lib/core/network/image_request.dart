/// 藏品图请求工具。
///
/// 1) **尺寸**（关键）：后端返回的 Wikimedia `Special:FilePath/<file>` 是
///    **全分辨率原图**（动辄数十 MB）。直接加载会在手机上超时/解码失败/爆内存
///    → 图显示不出来。Wikimedia 支持 `?width=N` 取**缩略图**（如 width=400 仅
///    ~50KB），用 [sizedImageUrl] 按显示尺寸取图。
/// 2) **User-Agent**：Wikimedia 对**空 UA** 返回 403（实测）；带任意非空 UA 即可。
///    dart:io 默认会带 `Dart/x.y (dart:io)`（实测亦 200），故 UA 非瓶颈，但仍按
///    Wikimedia UA 政策带一个合规描述性 UA 以示规范。
///
/// 长期更稳的方案是后端把图自存 R2（ObjectImage.image_key），返 R2 直链；届时
/// 这些链接不再是 Special:FilePath，[sizedImageUrl] 会原样返回、不受影响。
library;

const String kImageUserAgent =
    'GoMuseumBot/0.1 (https://gomuseum.app; contact appcraft008@gmail.com)';

const Map<String, String> kImageRequestHeaders = {
  'User-Agent': kImageUserAgent,
};

/// 给 Wikimedia `Special:FilePath` 链接加上目标宽度，取缩略图而非原图。
/// 非 Special:FilePath（如将来 R2 直链）或已带 width 的链接原样返回。
String sizedImageUrl(String url, int width) {
  if (!url.contains('Special:FilePath')) return url;
  if (url.contains('width=')) return url;
  final sep = url.contains('?') ? '&' : '?';
  return '$url${sep}width=$width';
}
