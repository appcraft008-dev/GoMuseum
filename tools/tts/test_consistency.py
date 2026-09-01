"""一致性打分函数的正负样本自检(契约纪律 18)。

**为什么用真实语料而不是造的样本**:配方 §六 把「用合成样本验证打分函数」
列为已验证失败的方法 —— 高度重复的假文本掩盖 autojunk 效应,测不出 bug。
`fixtures/` 里是 2026-09-01 橘园第二批的真实产物:prod 上的讲解原文 +
mlx-whisper 对我们自己生成的音频的实际转写。

每个用例都对应一次**真实发生过**的静默故障,不是想象出来的边界情况。
"""

import json
import pathlib

import pytest

from consistency import consistency, length_ratio, normalize

FIX = pathlib.Path(__file__).parent / "fixtures"


def _load(name):
    d = json.loads((FIX / f"{name}.json").read_text(encoding="utf-8"))
    return d["text"], d["transcript"]


# ---------- ① autojunk:拉丁语系上的灾难 ----------

def test_autojunk_real_french():
    """difflib 默认 autojunk=True 会把这条真实法语样本判成 0.18(真值 0.99)。

    机制:序列 ≥200 元素时,出现频率 >1% 的元素被当噪声丢弃。938 字的法语,
    1% 门槛只有 9 次 —— 26 个字母几乎全部超标,于是绝大多数字符被丢掉。
    后果不是「分数不准」而是**合格音频被判失败 → 重试 3 次 → 永久无音频**。
    """
    src, tr = _load("fr_analysis_real")
    assert len(normalize(src)) > 200, "样本必须够长才能触发 autojunk,否则这个测试是假的"
    assert consistency(src, tr) > 0.95

    # 控制组:证明这条测试真的在守 autojunk,而不是碰巧通过
    import difflib
    naive = difflib.SequenceMatcher(
        None, normalize(src), normalize(tr), autojunk=True
    ).ratio()
    assert naive < 0.5, f"预期 autojunk=True 会崩,实测 {naive} —— 样本可能被换过"


# ---------- ② 归一化必须做的(纪律 14) ----------

@pytest.mark.parametrize(
    "a,b",
    [
        ("Tómate", "Tomate"),                    # es:真实一致 1.00 曾被算成 0.53
        ("Édouard Manet", "Edouard Manet"),      # fr
        ("花點時間仔細欣賞", "花点时间仔细欣赏"),  # 繁体音频被 Whisper 转成简体
    ],
)
def test_normalization_absorbs_writing_variants(a, b):
    assert consistency(a, b) == 1.0


def test_real_japanese_pair_scores_high():
    """真实 ja 样本:音频合格,分数应在门槛(0.90)之上。"""
    src, tr = _load("ja_analysis_real")
    assert consistency(src, tr) >= 0.90


# ---------- ③ 归一化不能做的(纪律 25) ----------

@pytest.mark.parametrize(
    "a,b",
    [
        ("じっくり", "つっくり"),      # 配方记载的 ZH 种子真实故障形态
        ("アメデオ", "アメテオ"),      # 人名浊音
        ("ばば", "ぱぱ"),              # 浊/半浊
        ("だいがく", "たいかく"),      # 浊音 + 送气
    ],
)
def test_japanese_voicing_is_not_erased(a, b):
    """浊点在日语里是**音位**不是装饰。删掉它 = 浊音读错这一整类对检查完全隐形。

    要害:音色配方定 ja 用 EN 种子的唯一理由就是「ZH 种子浊音念错」——
    这几条如果得 1.0,把关那条决策的闸门就瞎在它自己所依据的维度上。
    """
    assert consistency(a, b) < 1.0


def test_korean_untouched_by_the_japanese_fix():
    """回归守卫:修浊点**不得**改动韩语。

    第一版修法图省事用了全局 NFKC,浊点是合回去了,但顺带把谚文 Jamo 也合成
    音节(한→한,长度 3→1),控制组实测 ko 有 12 条分数跟着漂移。
    韩语在这里应保持**分解**形态:한국어 = ㅎㅏㄴ ㄱㅜㄱ ㅇㅓ = 8 个字素。
    这个数字变了就说明有人又加了全局重组。
    """
    assert len(normalize("한국어")) == 8


# ---------- ④ 长度比:独立于一致性的那道门 ----------

def test_length_ratio_catches_repetition():
    """复读崩坏时一致性可能还不算太低,长度比会直接暴露。

    实测:崩坏的德语那条转写 1547 字 vs 原文 1070 字(比值 1.45),
    末尾把同一句复读了十几遍。有了这道独立的门,一致性阈值才敢按语言分档。
    """
    src, tr = _load("fr_analysis_real")
    assert 0.9 < length_ratio(src, tr) < 1.1
    assert length_ratio(src, tr + tr) > 1.8
