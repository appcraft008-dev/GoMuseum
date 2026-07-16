/// 讲解 TTS 懒生成端点结果（区分 就绪 / 文字未生成(404) / 生成失败(503)）。
library;

sealed class GuideAudioResult {
  const GuideAudioResult();
}

/// 200：音频就绪，可播放。
class GuideAudioReady extends GuideAudioResult {
  const GuideAudioReady(this.url);
  final String url;
}

/// 200 audio/mpeg：流式字节流（边生成边播）。仅 /audio/stream 端点返回。
/// [bytes] 是渐进到达的音频 chunk 流，喂给渐进播放源；异常时调用方回退老 /audio。
class GuideAudioStream extends GuideAudioResult {
  const GuideAudioStream(this.bytes);
  final Stream<List<int>> bytes;
}

/// 409 audio_generating：正在现场生成（撞段级锁）→ 非错误，等一下自动重试。
class GuideAudioGenerating extends GuideAudioResult {
  const GuideAudioGenerating();
}

/// 404 no_published_text：该语言 guide 文字还没生成 → 「讲解生成后可听」，非错误。
class GuideAudioNotReady extends GuideAudioResult {
  const GuideAudioNotReady();
}

/// 503 tts_failed 或网络/其它：音频暂不可用，可重试；不阻塞文字。
class GuideAudioFailed extends GuideAudioResult {
  const GuideAudioFailed();
}
