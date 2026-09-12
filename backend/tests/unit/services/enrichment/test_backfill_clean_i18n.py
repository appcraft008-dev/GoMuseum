"""显示名清洗:尾部消歧括号只按白名单剥,标题/名字自带的括号必须留。

全库实测(2026-09-01):27206 件藏品里 2906 个标题带馆藏编号、1907 个带生卒年份、
约 3500 个带作者名消歧后缀 —— 用户在馆藏列表看到的就是「투우 (마네)」。
但同样有 3000+ 个括号是**标题的一部分**(高更《餐（香蕉）》),通用剥离会削掉它们。
"""

from app.services.enrichment.backfill import _clean_i18n, strip_disambiguator

MANET = {"Édouard Manet", "마네", "爱德华·马奈"}
VERMEER = {"Johannes Vermeer", "Vermeer", "Jan Vermeer"}
GAUGUIN = {"Paul Gauguin", "保罗·高更"}


def test_strips_catalog_number():
    assert strip_disambiguator("olpé (E 647)") == "olpé"
    assert strip_disambiguator("Autoportret (F 627)") == "Autoportret"


def test_strips_life_dates_and_year():
    assert (
        strip_disambiguator("Porträt von Bossuet (1627-1704)") == "Porträt von Bossuet"
    )
    assert (
        strip_disambiguator("Autorretrato de Van Gogh (1889)")
        == "Autorretrato de Van Gogh"
    )


def test_strips_artist_name_disambiguator():
    assert strip_disambiguator("투우 (마네)", MANET) == "투우"
    assert (
        strip_disambiguator("聖母の誕生 (ムリーリョ)", {"ムリーリョ"}) == "聖母の誕生"
    )


def test_strips_kind_word_disambiguator():
    assert strip_disambiguator("Koronczarka (obraz Vermeera)", VERMEER) == "Koronczarka"
    assert strip_disambiguator("Verwundeter Kürassier (Öl)") == "Verwundeter Kürassier"
    assert strip_disambiguator("Henri Vidal (escultor)") == "Henri Vidal"


def test_keeps_parenthesis_that_is_part_of_the_title():
    """高更《餐（香蕉）》—— 括号就是标题的一部分,剥掉就成了另一幅画。"""
    assert strip_disambiguator("餐（香蕉）", GAUGUIN) == "餐（香蕉）"
    assert strip_disambiguator("Die Mahlzeit (Mahl mit Bananen)", GAUGUIN) == (
        "Die Mahlzeit (Mahl mit Bananen)"
    )
    assert strip_disambiguator("Esquisse de l'escalier Mollien (Apollon)") == (
        "Esquisse de l'escalier Mollien (Apollon)"
    )


def test_keeps_elder_younger_in_artist_names():
    """清洗**作者名**时不传 artist_names —— 「（長者）」是名字的一部分,不是消歧。"""
    assert _clean_i18n({"zh-hant": "巴塞洛繆斯·布呂恩（長者）"}) == {
        "zh-hant": "巴塞洛繆斯·布呂恩（長者）"
    }
    assert strip_disambiguator("Bruegel (der Ältere)") == "Bruegel (der Ältere)"


def test_kind_word_needs_whole_word_not_substring():
    """子串匹配会让 (Kölner Meister) 撞上 'öl'、(boiler) 撞上 'oil'。"""
    assert strip_disambiguator("Madonna (Kölner Meister)") == "Madonna (Kölner Meister)"
    assert strip_disambiguator("Study (boiler)") == "Study (boiler)"


def test_clean_i18n_drops_untranslated_cjk_and_extends_to_ja_ko():
    """非拉丁语言位没有本族文字 = 翻译失败残留,当缺失重解析(原本只查 zh)。"""
    out = _clean_i18n(
        {
            "zh": "Mihály Munkácsy",
            "ja": "Gaston Lecreux",
            "ko": "Gaston Lecreux",
            "zh-hant": "牧羊人的朝拜",
            "fr": "Le Repas",
        }
    )
    assert "zh" not in out and "ja" not in out and "ko" not in out
    assert out["zh-hant"] == "牧羊人的朝拜"
    assert out["fr"] == "Le Repas"  # 拉丁语言不受此规则影响


def test_clean_i18n_threads_artist_names_into_stripping():
    assert _clean_i18n({"ko": "투우 (마네)"}, MANET) == {"ko": "투우"}
    assert _clean_i18n({"ko": "투우 (마네)"}) == {
        "ko": "투우 (마네)"
    }  # 不给作者名就不剥


def test_strips_only_wrapping_quotes_not_one_sided():
    """引号在标题**中间**时不能动 —— 单侧剥会留下孤引号。

    prod 实测 565 个标题因此不配对(2026-09-01):
        Coupe à décor dit "grain de riz"  →  Coupe à décor dit "grain de riz
    根因是 str.strip(引号集) 语义是「两端各自独立地剥」,不是「剥成对的外层引号」。
    """
    from app.services.enrichment.backfill import _strip_wrapping_quotes

    # 中间带引号 → 原样保留
    for s in (
        'Coupe à décor dit "grain de riz"',
        'Tapis dit "Holbein à petits motifs"',
        'Afrodita, tipo de la "Venus Esquilina"',
    ):
        assert _strip_wrapping_quotes(s) == s

    # 真正的外层包裹 → 剥掉
    assert _strip_wrapping_quotes("《睡莲》") == "睡莲"
    assert _strip_wrapping_quotes('"Olympia"') == "Olympia"
    assert _strip_wrapping_quotes("「玩紙牌者」") == "玩紙牌者"
    assert _strip_wrapping_quotes("“Le Bain”") == "Le Bain"

    # 只有一侧 → 不动(宁可漏,不可伤)
    assert _strip_wrapping_quotes('"Olympia') == '"Olympia'
    assert _strip_wrapping_quotes('Olympia"') == 'Olympia"'


def test_clean_i18n_preserves_inner_quotes():
    from app.services.enrichment.backfill import _clean_i18n

    t = 'Coupe à décor dit "grain de riz"'
    assert _clean_i18n({"fr": t}) == {"fr": t}


def test_authoritative_facts_override_stored_ones():
    """权威标签必须压过库里已有 —— 顺序曾经是反的,于是某语言第一次抓到 1 条
    就永久锁死(实测 prod:zh 卡在 1 条,而 Wikidata 有 4 条),names 重跑修不好。
    docstring 一直写的是「权威标签优先」,代码没照做。"""
    from types import SimpleNamespace

    from app.services.enrichment.backfill import fill_artist_i18n_facts

    art = SimpleNamespace(
        nationality="France",
        nationality_i18n={"zh": "法國"},  # 陈旧(繁体,该被权威简体覆盖)
        notable_works=["Olympia"],
        notable_works_i18n={"zh": ["奥林匹亚"]},  # 陈旧:只有 1 条
    )
    data = {
        "nationality_i18n": {"zh": "法国"},
        "notable_works_i18n": {"zh": ["奥林匹亚", "草地上的午餐", "吹笛少年"]},
    }
    changed = fill_artist_i18n_facts(art, ["zh"], translator=None, data=data)
    assert changed
    assert art.nationality_i18n["zh"] == "法国"
    assert art.notable_works_i18n["zh"] == ["奥林匹亚", "草地上的午餐", "吹笛少年"]


def test_stored_language_kept_when_authority_has_none():
    """反向:权威源没有这个语言时,库里已有的不能被抹掉。"""
    from types import SimpleNamespace

    from app.services.enrichment.backfill import fill_artist_i18n_facts

    art = SimpleNamespace(
        nationality="France",
        nationality_i18n={"ko": "프랑스"},
        notable_works=["Olympia"],
        notable_works_i18n={"ko": ["올랭피아"]},
    )
    fill_artist_i18n_facts(art, ["ko"], translator=None, data={})
    assert art.notable_works_i18n["ko"] == ["올랭피아"]
    assert art.nationality_i18n["ko"] == "프랑스"


class _Tr:
    """把任何输入标成 译<原文>,便于分辨哪几件被翻过。"""

    def __init__(self):
        self.calls = []

    def translate_name(self, text, lang):
        self.calls.append((text, lang))
        return f"译<{text}>"


def _artist():
    from types import SimpleNamespace

    return SimpleNamespace(
        nationality=None,
        nationality_i18n={},
        notable_works=None,
        notable_works_i18n={},
    )


def test_notable_works_translated_per_work_not_per_language():
    """有权威译名的那件必须原样保留(它才是真相源),只翻 fetch 回退成英文的那几件。
    旧行为是"整语言全翻或全不翻",于是中日韩看到的是半截外文列表。"""
    from app.services.enrichment.backfill import fill_artist_i18n_facts

    art, tr = _artist(), _Tr()
    data = {
        "notable_works_i18n": {
            "en": ["Olympia", "The Fifer"],
            "zh": ["奥林匹亚", "The Fifer"],  # 第 2 件 fetch 回退成了英文
        },
        "notable_works_labels": [
            {"en": "Olympia", "zh": "奥林匹亚"},  # 有权威中文标签
            {"en": "The Fifer"},  # 没有 → 该翻
        ],
    }
    fill_artist_i18n_facts(art, ["en", "zh"], tr, data)
    assert art.notable_works_i18n["zh"] == ["奥林匹亚", "译<The Fifer>"]
    assert art.notable_works_i18n["en"] == ["Olympia", "The Fifer"], "轴心语不该被翻"
    assert tr.calls == [("The Fifer", "zh")], f"只该翻缺译名的那一件,实际 {tr.calls}"


def test_notable_works_lengths_stay_equal_when_translation_fails():
    """翻译抛异常时留原文,绝不丢条目 —— 丢了列表就又长短不一,回到最初的 bug。"""
    from app.services.enrichment.backfill import fill_artist_i18n_facts

    class Boom:
        def translate_name(self, text, lang):
            raise RuntimeError("上游挂了")

    art = _artist()
    data = {
        "notable_works_i18n": {"en": ["A", "B"], "ja": ["A", "B"]},
        "notable_works_labels": [{"en": "A"}, {"en": "B"}],
    }
    fill_artist_i18n_facts(art, ["en", "ja"], Boom(), data)
    assert art.notable_works_i18n["ja"] == ["A", "B"]
    assert len(art.notable_works_i18n["ja"]) == len(art.notable_works_i18n["en"])


def test_no_crash_when_language_absent_and_no_work_labels():
    """两边都空时长度也相等 —— 直接 works[lang] 会 KeyError。
    真实触发路径:pipeline 的作者没有 P800 数据(per_work 为空),
    而目标语言也还没有任何代表作。CI 的集成测试抓到过一次。"""
    from app.services.enrichment.backfill import fill_artist_i18n_facts

    art, tr = _artist(), _Tr()
    art.nationality = "France"
    data = {"nationality_i18n": {"zh": "法国"}}  # 无 notable_works_*
    fill_artist_i18n_facts(art, ["en", "zh", "it"], tr, data)
    assert art.nationality_i18n["zh"] == "法国"


# ---- 上游标签里混进整条英文原名(2026-09-12,用户在繁体版卢浮宫列表上发现) ----
#
# Wikidata 的标签是人填的,偶尔有人把两种语言塞进同一个:
# Q1231009 的 zh-tw = "The Coronation of Napoleon《拿破崙的加冕圖》"(zh 标签却是干净的)。
#
# ⚠️ 下面这组**负样本**是这条清洗的全部难点:prod 全量普查里,CJK 显示名含拉丁连词的
# 共 37 条,**36 条完全合法**。按"含拉丁字母"剥会把它们全毁掉(同纪律 24 的教训),
# 所以判据是"完整包含 title_en",而它们的拉丁片段都不等于各自的 title_en。


def test_strips_english_title_embedded_in_cjk_label():
    """正样本:用户报的那条。剥完英文,外层书名号由既有清洗接手。"""
    got = _clean_i18n(
        {"zh-hant": "The Coronation of Napoleon《拿破崙的加冕圖》"},
        None,
        "The Coronation of Napoleon",
    )
    assert got == {"zh-hant": "拿破崙的加冕圖"}


def test_keeps_legitimate_latin_in_cjk_titles():
    """负样本组:全部摘自 prod 真实数据,一条都不许被剥。"""
    cases = [
        # 馆藏编号
        ("石碑碎片 Astitarhunza-AO 10829", "Fragment of a stele"),
        ("鱷魚 Shebek Ra-E 16358", "Crocodile"),
        # 人名 / 地名
        ("Mlle Joly 半身像", "Bust of Mlle Joly"),
        ("Étang-la-Ville的風景畫", "Landscape at Étang-la-Ville"),
        # 作品上的拉丁铭文,是内容不是残留
        ("手持第六誡拉丁文「NON OCCIDES」（不可殺人）的半身天使", "Bust of an angel"),
        # 外文原题副标
        ("沼澤地 (Le Marais)", "The Marsh"),
    ]
    for value, title_en in cases:
        assert _clean_i18n({"zh-hant": value}, None, title_en) == {"zh-hant": value}


def test_does_not_strip_when_nothing_would_be_left():
    """整条就等于英文名 = "没翻译",不归这条清洗管 ——
    剥了会得到空串,而空显示名比英文显示名糟得多。"""
    v = {"zh-hant": "The Coronation of Napoleon"}
    # 本族文字检查会把它当翻译失败丢弃,但绝不能是被剥成空串导致的
    assert _clean_i18n(v, None, "The Coronation of Napoleon") == {}


def test_artist_names_never_get_title_en_stripping():
    """清洗作者名时不传 title_en —— 作者的英文名与显示名重合是常态,
    传了会把「Jean-Baptiste 讓-巴蒂斯特」剥成半截。这里钉住默认不剥。"""
    v = {"zh-hant": "Jean-Baptiste 讓-巴蒂斯特"}
    assert _clean_i18n(v) == v
