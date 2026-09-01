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
