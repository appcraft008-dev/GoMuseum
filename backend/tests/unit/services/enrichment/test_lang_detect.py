import pytest

from app.services.enrichment.lang_detect import text_in_language


@pytest.mark.parametrize(
    "text,lang,expected",
    [
        ("这是一段完整的中文讲解，介绍这幅画的历史与技法内容。", "zh", True),
        ("This is a complete English paragraph about the painting here.", "en", True),
        (
            "Claude Monet, né en 1840 à Paris, est un peintre français reconnu.",
            "en",
            False,
        ),
        ("约翰·施洗者的 severed head 悬浮在空中，这是一段较长的中文讲解。", "zh", True),
        ("What did Van Gogh's letters reveal about this piece of art?", "zh", False),
        ("Monet", "en", True),
        ("1855", "zh", True),
    ],
)
def test_text_in_language(text, lang, expected):
    assert text_in_language(text, lang) is expected


def test_language_agnostic_all_default_languages():
    from app.services.enrichment.lang_config import DEFAULT_LANGUAGES

    samples = {
        "en": "A long English sentence here about art history and painting technique.",
        "fr": "Une longue phrase française sur l'histoire de l'art et la technique picturale.",
        "de": "Ein langer deutscher Satz über Kunstgeschichte und Maltechnik steht hier.",
        "es": "Una larga frase en español sobre la historia del arte y la técnica pictórica.",
        "it": "Una lunga frase italiana sulla storia dell'arte e la tecnica pittorica qui.",
        "pl": "Długie polskie zdanie o historii sztuki i technice malarskiej tutaj przedstawione.",
        "zh": "这是一段较长的中文文本，讲述艺术史与绘画技法的相关内容。",
        "zh-hant": "這是一段較長的中文文本，講述藝術史與繪畫技法的相關內容。",
        "ja": "これは美術史と絵画技法について述べる、やや長めの日本語の文章です。",
        "ko": "이것은 미술사와 회화 기법에 대해 설명하는 다소 긴 한국어 문장입니다.",
    }
    for lang in DEFAULT_LANGUAGES:
        assert text_in_language(samples[lang], lang) is True, lang


# ---- 简繁互串(样本全部取自 prod 实测,不用合成语料)----
# 判定工具必须拿真实正负样本自检(纪律 18)。这里的每一条都有出处:
# 正样本 = prod zh-hant 位真漏出去的简体字;负样本 = 朴素判据在 prod 上误伤的字。


def test_simplified_only_table_is_not_empty():
    """字表路径在 opencc 包内部,版本升级挪了位置就会静默退化成'不判简繁'。

    没有这条断言,那种失效下**所有测试照绿**,而闸已经不工作了。
    """
    from app.services.enrichment.lang_detect import simplified_only

    simp = simplified_only()
    assert len(simp) > 3000, f"简体专有字表只有 {len(simp)} 个,字表大概率没读到"
    for c in "图们东国这时为龙尔员礼兰乐费机":
        assert c in simp, f"{c} 应被认作简体专有字"


@pytest.mark.parametrize(
    "char",
    # opencc 的 s2t 会把这些"纠"成古体/异体,但它们在繁体里本来就合法。
    # 朴素判据(s2t 转得动即简体)因此在 prod 2659 篇繁体正文里误伤 900 篇。
    list("里台后干范游占托岩斗郁厘征丑唇划栗吃辟凶采秘群床峰痴"),
)
def test_legit_traditional_chars_not_flagged(char):
    from app.services.enrichment.lang_detect import simplified_only

    assert char not in simplified_only(), f"{char} 是合法繁体字,不该判成简体"


@pytest.mark.parametrize(
    "text,lang,expected",
    [
        # prod 真实污染:繁体正文/标题里漏出个别简体字
        ("蘇薩廢墟全景图", "zh-hant", False),  # 图 应作 圖
        ("軍營中的騎士们", "zh-hant", False),  # 们 应作 們
        ("在梳妝台前的蜜西亞，由费利克斯·瓦洛东所繪", "zh-hant", False),
        ("聖奧古斯丁的祝聖礼", "zh-hant", False),  # 礼 应作 禮
        # 干净的繁体:含上面那批"合法繁体字",不能被误杀
        ("蒙兀兒帝國列王紀", "zh-hant", True),
        ("這幅畫裡的祕密與群像,擺在臺北的床邊", "zh-hant", True),
        ("秘密的山峰上有一群人", "zh-hant", True),
        # zh 位:繁体专有字进来要判否
        ("這幅畫的國別", "zh", False),
        ("这幅画的国别", "zh", True),
        # 短文本豁免不适用于简繁 —— 漏出去的 372 条标题全是短的
        ("全景图", "zh-hant", False),
        ("全景圖", "zh-hant", True),
        # 简繁同形的名字:两边都合法,不判否(fail-open)
        ("克洛德·莫奈", "zh-hant", True),
        ("克洛德·莫奈", "zh", True),
    ],
)
def test_han_script_crossover(text, lang, expected):
    assert text_in_language(text, lang) is expected


@pytest.mark.parametrize(
    "src,want",
    [
        ("蘇薩廢墟全景图", "蘇薩廢墟全景圖"),
        ("軍營中的騎士们", "軍營中的騎士們"),
        ("阿耳忒弥斯裝飾的油瓶", "阿耳忒彌斯裝飾的油瓶"),
        ("家庭肖像画", "家庭肖像畫"),
        # 合法繁体字一个都不许动(整串 s2t 会把它们改掉,定点转换不会)
        ("這幅畫裡的祕密與群像", "這幅畫裡的祕密與群像"),
        ("秘密的山峰上有一群人在床邊", "秘密的山峰上有一群人在床邊"),
        # 多候选字靠词组消歧:发→發/髮 两个方向都要对
        ("他发现了头发", "他發現了頭髮"),
        ("", ""),
    ],
)
def test_to_traditional(src, want):
    from app.services.enrichment.lang_detect import to_traditional

    assert to_traditional(src) == want
