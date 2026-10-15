"""PCM(s16le / 24 kHz / mono)→ 160 kbps MP3。

160 不是随便选的:质量闸 `audio_quality.estimate_duration_sec` 按「字节 ÷ 160 kbps」估时长,
低码率落库会让将来 VoxCPM2 替换时被 `deviates_from_existing` 拦下(spec §2.4)。
lameenc 两个坑(已复现):奇数字节 → `Input data must be 16-bit PCM data`;
没 encode 过就 flush → `Not currently encoding`。
"""

from app.core.exceptions import AIServiceException


class Mp3Encoder:
    SAMPLE_RATE = 24000
    BITRATE_KBPS = 160

    def __init__(self):
        import lameenc

        self._enc = lameenc.Encoder()
        self._enc.set_bit_rate(self.BITRATE_KBPS)
        self._enc.set_in_sample_rate(self.SAMPLE_RATE)
        self._enc.set_channels(1)
        self._enc.set_quality(2)
        self._rest = b""
        self.pcm_bytes = 0

    def encode(self, pcm: bytes) -> bytes:
        data = self._rest + pcm
        even = len(data) - len(data) % 2
        self._rest = data[even:]
        if not even:
            return b""
        self.pcm_bytes += even
        return bytes(self._enc.encode(data[:even]))

    def flush(self) -> bytes:
        if not self.pcm_bytes:
            raise AIServiceException("TTS 没有返回音频")
        return bytes(self._enc.flush())
