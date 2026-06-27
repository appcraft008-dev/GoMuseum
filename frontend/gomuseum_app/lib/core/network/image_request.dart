/// 公共图床（Wikimedia Commons 等）按 User-Agent 策略限流：
/// Flutter 默认图片请求 UA 会被 403 拦截。统一给所有藏品图请求带
/// 一个符合 Wikimedia UA 政策的描述性 User-Agent。
///
/// 长期更稳的方案是后端把图自存到 R2（ObjectImage.image_key），届时
/// 前端改读 R2 直链即可，此 header 仅为过渡。
library;

const Map<String, String> kImageRequestHeaders = {
  'User-Agent':
      'GoMuseumBot/0.1 (https://gomuseum.app; contact appcraft008@gmail.com)',
};
