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

from consistency import consistency, length_ratio, normalize, tts_input

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


# ---------- ⑤ zh-hant 喂简体:输入侧适配 ----------

# prod 上 Q3745385《紅髮女孩》讲解的开头,三个词在繁体音频里都念错了
# (whisper-small 与 large-v3 独立转写结论一致),同样的词在简体音频里全对。
_HANT_OPENING = "花點時間仔細欣賞亞美迪歐·莫迪裏安尼的「紅髮女孩」。注意她那鮮豔的頭髮"


def test_zh_hant_喂给模型的是简体():
    out = tts_input(_HANT_OPENING, "zh-hant")
    for 词 in ("仔细欣赏", "红发女孩", "鲜艳", "头发"):
        assert 词 in out, f"{词} 没转过来,模型还是会拿到它认不全的繁体字形"
    assert "繁" not in out and "鮮豔" not in out


def test_转换不改变字数():
    """atempo 用 len(text) 反推目标时长,字数一变语速对齐就跟着漂。"""
    assert len(tts_input(_HANT_OPENING, "zh-hant")) == len(_HANT_OPENING)


@pytest.mark.parametrize(
    "lang,text",
    [
        ("zh", "花点时间仔细欣赏"),
        ("en", "Take a moment to appreciate"),
        # 🔴 这条是这个语言开关存在的真正理由:日语正文里全是汉字,
        # 一旦漏了 lang 判断,OpenCC 会把「藝術」改成「艺术」——
        # 那是中文简化字,日语里根本没有这个写法,等于把日语文本改坏。
        ("ja", "アメデオ・モディリアーニの藝術"),
    ],
)
def test_只有zh_hant被改_其余语言原样(lang, text):
    assert tts_input(text, lang) == text


def test_run_batch_真的把_tts_input_接在生成那一行上():
    """⚠️ 这条守的是**调用点**,不是函数。

    上面几条全部只证明 `tts_input` 自己是对的 —— 而它在 `run_batch.py` 里
    被不被调用,它们一个都管不着。本项目已经在同一个形状上栽过:
    测试拿自己搭的假页面/假票据做断言,把产品代码改回坏的照样绿(配方 §六)。

    这里只能做**源码级**检查:生成那一步要跑真模型,CI 上装不了 voxcpm/torch,
    连 import run_batch 都做不到。所以读文本、断言那一行的形状。
    粗糙,但它能抓住"有人把接线撤了"这唯一一件事,而那正是会静默发生的事
    —— 撤掉之后繁体音频照样产出、照样过闸(重试几次总能过),只是又开始念错字。
    """
    src = (pathlib.Path(__file__).parent / "run_batch.py").read_text(encoding="utf-8")
    assert "from consistency import" in src and "tts_input" in src, \
        "run_batch.py 没有引入 tts_input"
    assert "m.generate(text=tts_input(text, lang)" in src, \
        "生成那一行没有走 tts_input —— zh-hant 又会拿繁体字形去念(实测 3 个词全错)"


def test_质检基准仍是原始繁体正文():
    """转换只在喂模型那一步。转写回来仍拿**繁体原文**打分,口径没跟着输入走。

    normalize() 本来就两侧都转简体,所以这条恒等式成立 —— 也就是说
    这个改动对三道闸门的读数**零影响**,不需要重新标定任何阈值。
    """
    转写 = "花点时间仔细欣赏亚美迪欧莫迪里安尼的红发女孩"
    assert consistency(_HANT_OPENING, 转写) == consistency(
        tts_input(_HANT_OPENING, "zh-hant"), 转写
    )
