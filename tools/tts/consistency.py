"""内容一致性打分 —— 判断「音频念的和原文是不是同一段内容」。

**独立成模块的理由不是整洁,是这段逻辑已经静默坏过三次**,而且每次的表现
都是「看起来在正常工作」:

| 时间 | 缺陷 | 症状 |
|---|---|---|
| 2026-08 | `SequenceMatcher` 默认 `autojunk=True` | 内容完全正确的转写得 0.50(真值 0.99),重试 3 次后判失败 |
| 2026-08 | 比对前不做归一化 | 繁体音频被转成简体 → 0.50;`Tómate` vs `Tomate` → 0.53 |
| 2026-09 | 归一化把日语浊点也删了 | `アメデオ` vs `アメテオ` 得 **1.000**,浊音读错完全隐形 |

坏检查比没有检查更糟:它一边烧算力,一边把合格内容永久标成失败 —— 三万段
规模上是灾难级的。所以这里的每个决定都写明原因,并由 `test_consistency.py`
用**真实语料**的正负样本守住(合成样本测不出 autojunk,见配方 §六)。

对应契约纪律:14(必须归一化)、18(判定工具先自检)、25(归一化会删掉信号)。
"""

from __future__ import annotations

import difflib
import re
import unicodedata

from opencc import OpenCC

_CC = OpenCC("t2s")

# 浊点/半浊点。在日语里是**音位**(か/が 是两个音),不是拉丁语系那种装饰性变音符。
_VOICE = "゙゚"
_KANA_VOICED = re.compile("[぀-ヿ][゙゚]")


def normalize(s: str) -> str:
    """比对前归一化。三步各自对应一类实测误判,缺一不可 —— 但第②步对日语要让路。

    ① 繁→简:Whisper 常把繁体音频转写成简体字,码位全不同 → 实测 0.50 被误判,
       归一化后 0.90(内容其实完全正确)。
    ② 去变音符(é→e / ö→o):es/de/it/fr/pl 系统性受害 —— 实测 es 真实一致 1.00
       被算成 0.53,纯粹因为 `Tómate` vs `Tomate`。
    ③ 小写 + 只留字母数字:去掉引号/标点差异。

    🔴 **②对日语必须让路**(契约纪律 25)。NFKD 把 `デ` 拆成 `テ`+U+3099(浊点),
    浊点是 combining 字符,于是被②一并删掉 —— **日语浊音读错这一整类错误就此
    对一致性检查完全隐形**(实测 `アメデオ` vs `アメテオ`、`ばば` vs `ぱぱ`
    全部得 1.000)。要害在于它瞎的位置:音色配方定 ja 用 EN 种子的**唯一理由**
    就是「ZH 种子浊音念错(じっくり→つっくり)」,把关那条决策的闸门,恰好瞎在
    那条决策所依据的维度上。

    ⚠️ 修法只能**定点**把假名的浊点合回去,**不能用全局 NFKC** —— 那会把谚文
    Jamo 也合成音节(한→한,长度 3→1),ko 的一致性和长度比全部漂移。
    控制组实测:全局 NFKC 时 ja 变 13 条、**ko 跟着变了 12 条**;定点重组后只有 ja 变。
    """
    s = _CC.convert(s)
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c) or c in _VOICE)
    s = _KANA_VOICED.sub(lambda m: unicodedata.normalize("NFC", m.group(0)), s)
    return "".join(c for c in s.lower() if c.isalnum())


def consistency(source: str, transcript: str) -> float:
    """原文与转写的相似度,[0, 1]。**`autojunk=False` 不是可选项。**

    difflib 默认 `autojunk=True`:序列 ≥200 个元素时,把出现频率 >1% 的元素当
    噪声丢弃。1116 字的法语文本,1% 门槛只有 11 次 —— 几乎每个字母都超,于是
    绝大多数字符被丢掉,分数直接崩一半。实测同一对文本:
    **`autojunk=True` 给 0.5027,`autojunk=False` 给 0.9946(真值)**。
    后果不是「分数不准」,而是合格音频被判失败 → 重试 3 次 → 仍标失败,
    那段内容永远不会有音频,同时烧掉 3 倍算力。
    """
    return difflib.SequenceMatcher(
        None, normalize(source), normalize(transcript), autojunk=False
    ).ratio()


def tts_input(text: str, lang: str) -> str:
    """喂给 TTS 的文本。**zh-hant 转成简体再念,显示给用户的正文一个字不改。**

    实测:VoxCPM2 认不全繁体专用字形,同一批词在简体正文里念得完全正确,
    在繁体正文里系统性念错(whisper-small 与 whisper-large-v3 独立转写、结论一致
    —— 两个模型听成同一个错音,就不是 ASR 的锅):

    | 原文 | 应读 | 繁体音频实际读作 | 同词的简体音频 |
    |---|---|---|---|
    | 仔細欣賞 | zǐxì xīnshǎng | shíxì xīnshǒu(实戏新手) | ✅ 正确 |
    | 紅髮女孩 | hóngfà nǚhái | tīngshàng nǚhái(听上女孩) | ✅ 正确 |
    | 鮮豔 | xiānyàn | xiānyù(鲜玉) | ✅ 正确 |

    简繁**同词同音**,所以这是纯粹的输入侧适配:不动正文 = 不改用户读到的字、
    不触发忠实度闸、不需要重新过任何内容闸。⚠️ 这一条很关键 —— 上一次为迁就
    TTS 去改正文(197×1690厘米 → 约2米×17米),忠实度闸判 False 只好撤回,
    而那道闸手工改是不会自己触发的(契约纪律 28 补充②)。

    ⚠️ t2s 是多对一,理论上会**制造**新的多音字(髮/發→发、幹/乾/干→干)。
    实测本语料 1177 种汉字里有 41 个属于这种合并,但这些字在简体正文里
    (149 条 zh 音频、一致性 0.937-0.958)本来就念对 —— 简体才是这个模型的主场。

    下游不用改:比对前 `normalize()` 本来就把两侧都转成简体,
    所以质检仍拿**原始繁体正文**当基准,口径没变。
    """
    return _CC.convert(text) if lang == "zh-hant" else text


def length_ratio(source: str, transcript: str) -> float:
    """转写字数 / 原文字数。**专抓复读崩坏与截断**,比一致性阈值更直接。

    实测:崩坏的那条德语转写 1547 字 vs 原文 1070 字(比值 1.45),末尾把同一句
    复读了十几遍。有了这道独立的门,一致性阈值才敢按语言分档 —— 否则为 CJK
    放宽阈值就等于给复读开了后门。
    """
    return len(normalize(transcript)) / max(len(normalize(source)), 1)
