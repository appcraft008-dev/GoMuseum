"""按**读音**判转写差异的性质 —— 一致性分数做不到的那一维。

一致性分数把下面两件事一视同仁地扣分:
    「盗」→「到」       拼音都是 dao4 → 同音字,ASR 选字问题,**音频是对的**
    「夕阳」→「的棋羊」  xi1yang2 vs de5qi2yang2 → **真念错**
所以它既证明不了"修好了",也证明不了"变坏了"。判重灌/换种子/改预处理
有没有效,必须用读音级比对,不能用分数(2026-09-09 繁体重灌实测:
按分数挑样本会得出**反向**结论,那道闸对字形念错近乎失明)。

⚠️ 工具本身要先过自检再信它 —— 见 test_reading_check.py 的已知同音/真错样本组。
「三人/散人」我曾亲手标成同音,自检当场否掉(さんにん/さんじん)。

⚠️ 仪器有底噪:日语侧拿**已接受的 tts-1 基准**量过,真错率约 45/千字。
低于底噪的差异说明不了任何事,别拿它下"某批音频质量差"的结论。
已知盲点(会被误记成"真错",两侧对照时应一并剔除):阿拉伯数字 vs 汉字数字
(「七」→「7」)、opencc 折不掉的异体字(「戴著」→「带着」)、片假名外来词拆分。

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


def classify(a, b, lang):
    """把一处差异归类:同音 / 仅声调(仅 zh)/ 真错。"""
    if _reading(a, lang) == _reading(b, lang):
        return "同音"
    if lang != "ja" and _reading(a, lang, tone=False) == _reading(b, lang, tone=False):
        return "仅声调"  # 声母韵母一致、调不同:听感有偏但不是念错别字
    return "真错"


def analyze(source, transcript, lang):
    """逐处差异归类。返回 (计数, 正文字数, 一致性分数, 真错样例)。

    ⚠️ `autojunk=False` 不能省:difflib 默认会把长文本里的高频字当"垃圾"跳过,
    正是这条默认值让打分函数在繁体上系统性失真过。
    """
    a, b = normalize(source), normalize(transcript)
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
    return n, len(a), consistency(source, transcript), detail


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
            n, ln, c, det = analyze(text, tr, wlang(j["language"]))
            tot[label]["真错"] += n["真错"]
            tot[label]["字"] += ln
            print(
                f"  {label}  一致性{c:.3f}  {ln}字  真错{n['真错']} "
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
