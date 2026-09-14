"""按**读音**判转写差异的性质 —— 一致性分数做不到的那一维。

一致性分数把下面两件事一视同仁地扣分:
    「盗」→「到」       拼音都是 dao4 → 同音字,ASR 选字问题,**音频是对的**
    「夕阳」→「的棋羊」  xi1yang2 vs de5qi2yang2 → **真念错**
所以它既证明不了"修好了",也证明不了"变坏了"。判重灌/换种子/改预处理
有没有效,必须用读音级比对,不能用分数(2026-09-09 繁体重灌实测:
按分数挑样本会得出**反向**结论,那道闸对字形念错近乎失明)。

⚠️ 工具本身要先过自检再信它 —— 见 test_reading_check.py 的已知同音/真错样本组。
「三人/散人」我曾亲手标成同音,自检当场否掉(さんにん/さんじん)。

⚠️ 仪器有底噪:日语侧拿**已接受的 tts-1 基准**量过,真错率 41/千字
(2026-09-14 用修好的口径重量;旧口径读数 45,差的就是下面这两处污染)。
低于底噪的差异说明不了任何事,别拿它下"某批音频质量差"的结论。
已知盲点(会被误记成"真错",两侧对照时应一并剔除):阿拉伯数字 vs 汉字数字
(「七」→「7」)、opencc 折不掉的异体字(「戴著」→「带着」)、片假名外来词拆分。

🔴 **这把尺子自己坏过两处,都是"看起来在正常工作"**(2026-09-14 查明):
① 归一化对日语也做繁→简,而 pykakasi 读不了简体 → 见 `_norm`;
② `classify` 拿 difflib 切出的**片段**去注音,而日语音训随词而变 → 见
`read_consistency`。两处都只抬高真错率、不降低,所以历史上凡是用它得出的
「日语真错率高」结论都偏严 —— 判种子/判闸之前先看 `read_consistency`。

用法(需 mlx_whisper,只能在生成机跑):
    reading_check.py <jobs.json> <新目录> [旧目录]
给了旧目录就是 A/B(同一段正文、同一工具,修复前后各一份)。
"""

import difflib
import sys

from consistency import consistency, normalize

_PINYIN = _KAKASI = None


def _reading(s, lang, tone=True):
    """把一段文字转成读音串。zh 用拼音(可带调),ja 用平假名。"""
    global _PINYIN, _KAKASI
    if lang == "ja":
        if _KAKASI is None:
            import pykakasi

            _KAKASI = pykakasi.kakasi()
        return "".join(x["hira"] for x in _KAKASI.convert(s))
    if _PINYIN is None:
        from pypinyin import Style, lazy_pinyin

        _PINYIN = (lazy_pinyin, Style)
    lazy_pinyin, Style = _PINYIN
    return lazy_pinyin(s, style=Style.TONE3 if tone else Style.NORMAL)


def _norm(s, lang):
    """诊断口径的归一化:日语**不做繁→简**。

    t2s 会把与繁体同形的日语汉字改写成简体(实测日语正文 5.84% 的字、231 种),
    而 pykakasi 读不了简体 —— 于是任何含此类字的差异都被 `classify` 判成「真错」。
    实测这一处污染让真错率虚高:过闸组 63.1→56.4、未过闸组 134.2→121.4(每千字)。
    ⚠️ 闸那一侧(`consistency()`)保持原样,理由见 `normalize` 的注释。
    """
    return normalize(s, t2s=(lang != "ja"))


def read_consistency(source, transcript, lang):
    """**整段**先转读音再比 —— 片段归类做不到的那一维。

    为什么不能只靠 `classify`:difflib 在**字面**上对齐,切出来的往往是半个词,
    而日语汉字的音训随词而变。单独注音拿到的是词典头条读音,不是它在词里的读音:

        「及」 在「および」里读 およ,单独注音读 きゅう  → 被判「真错」
        「家」 在「画家」  里读 か,  单独注音读 いえ    → 被判「真错」
        「聖」 在「聖ヨハネ」里读 せい,单独注音读 ひじり → 被判「真错」

    整段注音没有这个问题(上下文还在),所以它是判「音频念的对不对」时唯一
    不受写法影响的那个数。实测锚点(2026-09-14,whisper-small):

    | 组 | 读音一致性 | 真错/千字 |
    |---|---|---|
    | tts-1 日语基准(已被接受、线上服役,n=1) | 0.970 | 41.1 |
    | VoxCPM2 过闸组(n=92) | 0.963 | 55.5 |
    | VoxCPM2 未过闸组(n=8) | 0.923 | 122.1 |

    ⚠️ **它不是闸**,只是诊断。拿它去改闸之前要先有正负样本组
    (见 test_reading_check.py)和人耳/基准锚点 —— 单凭"分得开"不足以换闸。
    ⚠️ 已知盲点与字面分数相同:阿拉伯数字 vs 汉字数字(三↔3、十七↔17)两把尺子
    一样瞎,不是本函数引入的新问题。
    """
    a = "".join(c for c in _reading(source, lang) if c.isalnum())
    b = "".join(c for c in _reading(transcript, lang) if c.isalnum())
    return difflib.SequenceMatcher(None, a, b, autojunk=False).ratio()


def classify(a, b, lang):
    """把一处差异归类:同音 / 仅声调(仅 zh)/ 真错。"""
    if _reading(a, lang) == _reading(b, lang):
        return "同音"
    if lang != "ja" and _reading(a, lang, tone=False) == _reading(b, lang, tone=False):
        return "仅声调"  # 声母韵母一致、调不同:听感有偏但不是念错别字
    return "真错"


def analyze(source, transcript, lang):
    """逐处差异归类。返回 (计数, 正文字数, 一致性分数, 真错样例, 读音一致性)。

    ⚠️ `autojunk=False` 不能省:difflib 默认会把长文本里的高频字当"垃圾"跳过,
    正是这条默认值让打分函数在繁体上系统性失真过。
    ⚠️ 第 3 个返回值是**字面**一致性(与闸同口径,`consistency()` 原样),
    第 5 个是**整段读音**一致性 —— 两个都要看:字面的那个受写法影响。
    """
    a, b = _norm(source, lang), _norm(transcript, lang)
    n = {"同音": 0, "仅声调": 0, "真错": 0, "增删": 0}
    detail = []
    for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(
        None, a, b, autojunk=False
    ).get_opcodes():
        if tag == "equal":
            continue
        if tag != "replace":
            n["增删"] += max(i2 - i1, j2 - j1)
            continue
        x, y = a[i1:i2], b[j1:j2]
        k = classify(x, y, lang)
        n[k] += max(len(x), len(y))
        if k == "真错" and len(detail) < 8:
            detail.append(f"「{x[:20]}」→「{y[:20]}」")
    return (
        n,
        len(a),
        consistency(source, transcript),
        detail,
        read_consistency(source, transcript, lang),
    )


def _main():
    import json
    import os

    import mlx_whisper
    from fetch_text import fetch_text

    jobs = json.load(open(sys.argv[1]))
    dirs = [("新", sys.argv[2])] + ([("旧", sys.argv[3])] if len(sys.argv) > 3 else [])
    wlang = lambda l: "zh" if l == "zh-hant" else l  # noqa: E731
    tot = {label: {"真错": 0, "字": 0} for label, _ in dirs}

    for j in jobs:
        name = f"{j['qid']}__{j['language']}__{j['section']}.mp3"
        text = fetch_text(j)
        if not text:
            print(f"{name} 取不到正文,跳过")
            continue
        print(f"{'='*66}\n{name}")
        for label, d in dirs:
            p = os.path.join(d, name)
            if not os.path.exists(p):  # 未过闸的在 _rejected/ 里,一样要能查
                p = os.path.join(d, "_rejected", name)
            if not os.path.exists(p):
                print(f"  {label}: 文件缺失")
                continue
            tr = mlx_whisper.transcribe(
                p,
                path_or_hf_repo="mlx-community/whisper-small-mlx",
                language=wlang(j["language"]),
            )["text"].strip()
            n, ln, c, det, rc = analyze(text, tr, wlang(j["language"]))
            tot[label]["真错"] += n["真错"]
            tot[label]["字"] += ln
            print(
                f"  {label}  字面{c:.3f} 读音{rc:.3f}  {ln}字  真错{n['真错']} "
                f"仅声调{n['仅声调']} 同音{n['同音']} 增删{n['增删']}"
                f"  ({n['真错']/max(ln,1)*1000:.1f}/千字)"
            )
            for d2 in det[:3]:
                print(f"      {d2}")

    print(f"\n{'='*66}\n合计:")
    for k, v in tot.items():
        if v["字"]:
            print(
                f"  {k}  真错 {v['真错']} 处 / {v['字']} 字 "
                f"= 每千字 {v['真错']/v['字']*1000:.1f} 处"
            )


if __name__ == "__main__":
    _main()
