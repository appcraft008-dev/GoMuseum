"""读音级判定工具的自检 —— **判定工具先验证再信任**(契约纪律 18)。

这些样本组不是凑数:整条结论链(「zh-hant 喂简体让真错率降 6.2 倍」)全靠
classify 判得对。判错方向而不自知,得到的是一个看起来很有说服力的假结论。
"""

import pytest
from reading_check import analyze, classify

ZH = [
    # 同音字:ASR 选错字,音频本身是对的 —— 不该算念错
    ("盗", "到", "同音"),
    ("丽莎", "利沙", "同音"),
    ("急剧", "极具", "同音"),
    ("莫", "默", "同音"),
    ("吉维", "极为", "同音"),
    # 声母韵母一致、只有调不同
    ("睡", "水", "仅声调"),
    # 真念错:读音都不一样
    ("夕阳", "的棋羊", "真错"),
    ("睡莲", "瑞联", "真错"),
    ("瞬息", "顺序", "真错"),
]

JA = [
    ("意志", "意思", "同音"),
    ("機械", "機会", "同音"),
    ("公園", "講演", "同音"),
    ("科学", "化学", "同音"),
    ("橋", "箸", "同音"),
    ("雨", "飴", "同音"),
    ("誓い", "視界", "真错"),
    ("絵画", "海外", "真错"),
    ("彫刻", "彰国", "真错"),
    # ⚠️「三人/散人」我曾亲手标成同音,自检当场否掉(さんにん / さんじん)。
    # 保留为真错样本 —— 它是"工具比我准"的证据。
    ("三人", "散人", "真错"),
    ("キアロスクーロ", "空路", "真错"),
]


# ⚠️ 不用 importorskip:依赖缺失时**跳过就是绿的**,而 CI 把 skipped 当通过 ——
# 这道自检会静默消失,正好在最需要它的时候。缺依赖就让它红。
@pytest.mark.parametrize("a,b,want", ZH)
def test_classify_zh(a, b, want):
    assert classify(a, b, "zh") == want


@pytest.mark.parametrize("a,b,want", JA)
def test_classify_ja(a, b, want):
    assert classify(a, b, "ja") == want


def test_analyze_separates_homophone_from_real_error():
    """整段比对:同音处不计真错,真念错处要计到 —— 两侧都要验,只验一侧等于没验。"""
    src = "请仔细欣赏这幅睡莲,它画于吉维尼的花园"
    # 「睡莲」→「瑞联」是真念错;「吉维」→「极为」同音
    n, ln, _, det, rc = analyze(src, "请仔细欣赏这幅瑞联,它画于极为尼的花园", "zh")
    assert n["真错"] > 0, "真念错必须被抓到"
    assert det, "真错样例要留下来,否则事后无从复核"
    assert rc < 1.0, "读音级也要看得见这处真念错"
    # 同一段正文与自己比:零差异
    n0, _, _, _, rc0 = analyze(src, src, "zh")
    assert n0 == {"同音": 0, "仅声调": 0, "真错": 0, "增删": 0}
    assert rc0 == 1.0


# ─────────────────────────────────────────────────────────────────────────────
# 整段读音级分数(read_consistency)的正负样本组。
#
# 为什么单独一组:它是给「ja 一致性为什么低」这类判断用的,而那类判断一旦错,
# 代价是换错种子/改错闸,不是一条音频。正样本 = 纯写法差异(音频是对的,必须
# 几乎不扣分),负样本 = 真念错(必须扣分),两侧都要验 —— 只验一侧的话,
# 「判得准」和「判得松」长得一模一样。
# ─────────────────────────────────────────────────────────────────────────────

# 纯写法差异:音频念的是对的,读音级应当 ≈1.000(字面分数在这里只有 0.40-0.57)
JA_SAME_SOUND = [
    ("および", "及び", "送假名 vs 汉字"),
    ("わたって", "渡って", "同上"),
    ("碑文を読む", "ひぶんを読む", "汉字 vs 假名"),
]

# 真念错:读音级必须扣分。前三条是历史上把闸弄瞎过的浊音/半浊音类。
JA_REAL_ERROR = [
    ("じっくり見る", "つっくり見る", "浊音念错(定 ja 用 EN 种子的那一类)"),
    ("アメデオの肖像", "アメテオの肖像", "浊音念错(曾让一致性得 1.000)"),
    ("ばばという音", "ぱぱという音", "半浊音念错"),
    ("メデューズ号の筏", "メデューズ号のフォー", "汉字读错(2026-09-14 实测 11 处)"),
    ("皇妃の肖像", "コーヒーの肖像", "整词念错"),
    ("観る者を圧倒する", "絡むものを圧倒する", "整词念错"),
]


@pytest.mark.parametrize("a,b,why", JA_SAME_SOUND)
def test_read_consistency_ignores_orthography(a, b, why):
    from reading_check import read_consistency

    assert read_consistency(a, b, "ja") > 0.98, why


@pytest.mark.parametrize("a,b,why", JA_REAL_ERROR)
def test_read_consistency_catches_real_error(a, b, why):
    from reading_check import read_consistency

    assert read_consistency(a, b, "ja") < 0.98, why


def test_日语诊断不做繁简转换而闸那侧照做():
    """`_norm` 只在诊断口径去掉 t2s,**闸的口径一个字不能动**。

    两件事分开测,因为它们的错法不同:诊断这侧漏改 → 真错率虚高、结论跑偏;
    闸那侧被顺手改掉 → 线上过闸行为静默变化,而没有任何用例会红。
    """
    from consistency import normalize
    from reading_check import _norm

    s = "聖母の肖像は美術館にある"  # 聖/術 与繁体同形,t2s 会改写它们
    assert _norm(s, "ja") == normalize(s, t2s=False)
    assert _norm(s, "ja") != normalize(s), "日语诊断口径必须绕开 t2s"
    assert _norm(s, "zh") == normalize(s), "非日语不受影响"
    assert normalize(s) == normalize(s, t2s=True), "闸的默认口径不变"


def test_整段注音避开片段脱离上下文的误判():
    """同一处差异,片段归类判「真错」,整段读音判「没差」—— 后者才是对的。

    「および」→「及び」读音完全相同(および),但 difflib 切出的片段是
    「およ」→「及」,单独注音得 およ / きゅう,于是被判成念错。
    """
    from reading_check import classify, read_consistency

    assert classify("およ", "及", "ja") == "真错"  # 片段口径:误判
    assert read_consistency("および", "及び", "ja") == 1.0  # 整段口径:判对
