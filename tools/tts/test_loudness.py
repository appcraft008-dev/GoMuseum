"""响度归一的两条不变量:**永不削顶**、**量不到就别动**。

这两条比"增益算得准不准"重要得多。削顶是不可逆的音质损伤,而且**听起来只是"响了点"**
—— 三道质检门(锐度是比值、一致性是转写、长度比是字数)对它全部免疫,没有任何下游
能发现。所以护栏必须立在算增益这一步,并由测试钉死。

样本取自真实 ffmpeg 输出(Q28797622__zh-hant__significance,全库最轻的一条)。
"""

import pytest

from loudness import PEAK_CEIL_DBFS, TARGET_LUFS, gain_db, parse_ebur128

# 真实 ffmpeg ebur128 输出:逐帧行 + 末尾 Summary 块。
# 逐帧行里**也有** `I:` 和 `TPK:` —— 正则锚在行首才不会取到它们,
# 这段样本存在的意义就是钉住这一点(取到逐帧值 = 拿第一帧的 -70 去算增益)。
REAL = """[Parsed_ebur128_0 @ 0xa0d] t: 0.0999  TARGET:-23 LUFS    M:-120.7 S:-120.7     I: -70.0 LUFS       LRA:   0.0 LU  FTPK: -25.5 dBFS  TPK: -25.5 dBFS
[Parsed_ebur128_0 @ 0xa0d] t: 44.0999  TARGET:-23 LUFS    M: -36.9 S: -32.5     I: -32.3 LUFS       LRA:   4.3 LU  FTPK: -243.2 dBFS  TPK: -13.5 dBFS
[Parsed_ebur128_0 @ 0xa0d] Summary:

  Integrated loudness:
    I:         -32.3 LUFS
    Threshold: -42.5 LUFS

  Loudness range:
    LRA:         4.3 LU
    Threshold: -52.5 LUFS
    LRA low:   -35.1 LUFS
    LRA high:  -30.8 LUFS

  True peak:
    Peak:      -13.5 dBFS
"""

# 全静音时 ffmpeg 实测打的是 `I: -70.0` + `Peak: -inf`(不是两个都 -inf)。
SILENT = """  Integrated loudness:
    I:         -70.0 LUFS

  True peak:
    Peak:       -inf dBFS
"""


def test_只取_Summary_块不取逐帧行():
    assert parse_ebur128(REAL) == (-32.3, -13.5)


def test_峰值_inf_解析为None而不是崩掉():
    assert parse_ebur128(SILENT) == (-70.0, None)


def test_完全解析不出来时增益为零():
    assert gain_db(*parse_ebur128("ffmpeg: no such file")) == 0.0


@pytest.mark.parametrize(
    "lufs,peak",
    [
        (-32.3, -13.5),   # 全库最轻:够得到目标
        (-12.0, -0.5),    # 全库最响:要衰减 9dB
        (-26.3, -3.5),    # 波峰因数 22.8dB 的病态条目:够不到目标,被夹紧
        (-21.0, -3.0),    # 已在目标上
        (-45.0, -0.2),    # 极端:想加 24dB 但一点余量都没有
    ],
)
def test_施加增益后峰值永不超过天花板(lufs, peak):
    """核心不变量。破了它就等于在削顶,而削顶没有任何下游能发现。"""
    assert peak + gain_db(lufs, peak) <= PEAK_CEIL_DBFS + 1e-9


def test_有余量时就该真的对齐到目标():
    # 夹紧不能夹过头 —— 否则"归一"变成"永远只衰减",全库越跑越轻。
    assert gain_db(-32.3, -13.5) == pytest.approx(TARGET_LUFS - (-32.3))


def test_峰值未知时只许衰减不许加():
    assert gain_db(-40.0, None) == 0.0        # 想加 19dB,不敢加
    assert gain_db(-10.0, None) == pytest.approx(-11.0)   # 衰减不可能削顶,放行
