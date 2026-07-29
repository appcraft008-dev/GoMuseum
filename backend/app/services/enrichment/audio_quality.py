"""音频质量闸 —— **替换已有音频前必须过**。

拿一个自托管模型去覆盖已经能用的 tts-1 音频,是有下行风险的:模型回归会
**静默**毁掉整个音频库,而且不可逆(旧文件替换后成孤儿)。所以规则是:
**不过闸就不替换,保留旧版本。**

刻意不引入 librosa/ffmpeg 依赖:这些检查要在批量管线里跑几万次,
靠字节级估算就能抓住真正会出事的形态 —— 空音频、截断、无限重复。
真正的音色/发音质量由另一侧的设计种子与参数保证(见 memory
tts-selfhost-voxcpm-recipe),不是这里的职责。
"""

from __future__ import annotations

from dataclasses import dataclass

# 与现网一致:实测 R2 上的音频为 160 kbps 单声道 MP3
DEFAULT_BITRATE_BPS = 160_000

# 每分钟朗读字数(粗略,用于时长合理性)。CJK 按字,其余按词近似。
CHARS_PER_MIN = {
    "zh": 280,
    "zh-hant": 280,
    "ja": 300,
    "ko": 320,
}
DEFAULT_CHARS_PER_MIN = 900  # 拉丁语系按字符算,单位时间字符数高得多

# 时长偏离容忍区间。做宽:不同引擎语速本就有差异,这里只抓**数量级**错误
MIN_RATIO, MAX_RATIO = 0.45, 2.2

# 替换场景:与被替换版本的时长差异上限。同一段文本换引擎,时长不该差一倍
REPLACE_MAX_DEVIATION = 0.5


@dataclass(frozen=True)
class QualityVerdict:
    ok: bool
    reason: str
    duration_sec: float


def estimate_duration_sec(data: bytes, bitrate_bps: int = DEFAULT_BITRATE_BPS) -> float:
    return len(data) * 8 / bitrate_bps if data else 0.0


def expected_duration_sec(text: str, language: str) -> float:
    cpm = CHARS_PER_MIN.get(language, DEFAULT_CHARS_PER_MIN)
    return len(text or "") / cpm * 60 if text else 0.0


def check_audio(
    data: bytes,
    *,
    text: str,
    language: str,
    previous_duration_sec: float | None = None,
) -> QualityVerdict:
    """判定一段新生成的音频能否落库/替换。

    [previous_duration_sec] 给了就额外做替换偏差检查 —— 这是替换场景最有用的
    一条:同一段文本换引擎,时长差一倍必有问题(截断、重复、语速失控)。
    """
    dur = estimate_duration_sec(data)

    if not data or len(data) < 2_000:
        return QualityVerdict(False, "empty_or_too_small", dur)

    exp = expected_duration_sec(text, language)
    if exp <= 0:
        # 没有参照文本时只做存在性检查,不臆断
        return QualityVerdict(True, "ok_no_reference_text", dur)

    ratio = dur / exp
    if ratio < MIN_RATIO:
        # 最常见的真实故障:生成中途截断
        return QualityVerdict(False, f"too_short(ratio={ratio:.2f})", dur)
    if ratio > MAX_RATIO:
        # 无限重复/爆音的典型形态
        return QualityVerdict(False, f"too_long(ratio={ratio:.2f})", dur)

    if previous_duration_sec and previous_duration_sec > 0:
        dev = abs(dur - previous_duration_sec) / previous_duration_sec
        if dev > REPLACE_MAX_DEVIATION:
            return QualityVerdict(False, f"deviates_from_existing({dev:.0%})", dur)

    return QualityVerdict(True, "ok", dur)
