"""响度归一 —— 让同一件作品的各段音频音量一致。

**为什么需要**:三道质检门(锐度/一致性/长度比)对音量**完全免疫** —— 锐度是比值,
一致性是转写。于是响度偏差是唯一一个每条都在发生、却没有任何护栏的维度。
实测已灌入 prod 的 568 条(2026-09-08):

  同一件作品·同一语言内部的响度极差:中位 4.1 LU · p90 6.9 LU · **最大 15.3 LU**
  76% 的(作品,语言)组内落差 >3 LU;最糟的 Q28797622/zh-hant 组内 qa_0 −17.0 ↔
  significance −32.3 —— 用户连着听要中途去调手机音量。

**为什么是纯增益,不是 loudnorm**:`loudnorm` 默认带真峰限幅器,会改动态 ——
撞「任何加速/处理方案都不得以降低音质为代价」这条红线。这里只做乘法。

**为什么够不到目标就算了(夹紧)**:全库 568 条里有 3 条波峰因数达 22 dB(正常语音
12-18),是瞬态尖峰不是人声本体。让它们去定全局目标,就得把所有内容压到 −24 LUFS
(白白轻 3 dB)。夹紧后:−21 目标下 42/568 达不到,但组间极差 20.3 → **2.8 LU**,
p10-p90 直接归零,而中位音量与今天**完全一致**。
"""

from __future__ import annotations

import re
import subprocess

# 目标响度 = 已灌入 prod 那 568 条的**实测中位**(−21.1)。取这个值意味着
# 归一之后整体音量与今天一模一样,只是不再忽大忽小 —— 零音量回归。
TARGET_LUFS = -21.0
# 峰值天花板。留 1 dB 给 mp3 解码的真峰过冲(采样峰值 ≤ 真峰)。
PEAK_CEIL_DBFS = -1.0

_I = re.compile(r"^\s*I:\s*(-?[\d.]+)\s*LUFS", re.M)
_PEAK = re.compile(r"^\s*Peak:\s*(-?[\d.]+)\s*dBFS", re.M)


def parse_ebur128(stderr: str) -> tuple[float | None, float | None]:
    """从 ffmpeg ebur128 的 stderr 取 (整体响度 LUFS, 峰值 dBFS)。取不到返回 None。

    两个正则都**锚在行首**:逐帧日志里也有 `I:`/`FTPK:`/`TPK:`,但都跟在
    `t: … M: … S: …` 后面,不在行首 —— 只有末尾 Summary 块的才顶格(缩进后顶格)。
    再取 `[-1]` 双保险。
    静音段 ffmpeg 会打 `I: -inf LUFS`,数字正则匹配不上 → None → 增益 0。
    **失败方向必须是"不动它"**,而不是拿一个瞎猜的增益去改音频。
    """
    i, p = _I.findall(stderr), _PEAK.findall(stderr)
    return (float(i[-1]) if i else None, float(p[-1]) if p else None)


def gain_db(
    lufs: float | None,
    peak: float | None,
    target: float = TARGET_LUFS,
    ceil: float = PEAK_CEIL_DBFS,
) -> float:
    """把这条对齐到 target 所需的纯增益(dB),夹紧到峰值余量。

    `min(想要的增益, 顶得住的增益)` —— 所以**永远不会削顶,也永远不需要限幅器**。
    衰减方向不受峰值约束(变轻不可能削顶),min 天然处理:想衰减时第一项为负,
    第二项(余量)通常为正,取 min 就是那个负数。
    量不到(None)一律返回 0.0:不确定时不动音频。
    """
    if lufs is None:
        return 0.0
    want = target - lufs
    if peak is None:
        return min(want, 0.0)  # 峰值未知 → 只允许衰减,不敢加
    return min(want, ceil - peak)


def measure(path, atempo: float) -> tuple[float | None, float | None]:
    """量**变速之后**的响度与峰值(不落盘,`-f null`)。

    必须带上 atempo 一起量:变速会改变响度,拿变速前的数去算增益就对不上了。
    """
    out = subprocess.run(
        [
            "ffmpeg",
            "-hide_banner",
            "-nostats",
            "-i",
            str(path),
            "-filter:a",
            f"atempo={atempo:.4f},ebur128=peak=true",
            "-f",
            "null",
            "-",
        ],
        capture_output=True,
        text=True,
    )
    return parse_ebur128(out.stderr)
