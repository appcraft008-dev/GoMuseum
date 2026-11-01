"""网站十语文案(spec 2026-10-22-website-v1 §九):键齐、不写死馆名、格式化不炸。"""

import string

import pytest

from app.services.enrichment.catalog import MuseumCatalog
from app.services.enrichment.factory import CATALOG_PATH
from app.services.website.copy import COPY, t
from app.services.website.data import LANGS


def test_every_language_has_every_key():
    assert set(COPY) == set(LANGS)
    for lang in LANGS:
        assert set(COPY[lang]) == set(COPY["en"]), lang
        assert all(v.strip() for v in COPY[lang].values()), lang


def test_placeholders_match_english():
    fmt = string.Formatter()
    for key, en in COPY["en"].items():
        want = {f for _, f, _, _ in fmt.parse(en) if f}
        for lang in LANGS:
            got = {f for _, f, _, _ in fmt.parse(COPY[lang][key]) if f}
            assert got == want, (lang, key)


def test_no_hardcoded_museum_names():
    names = set()
    for cfg in MuseumCatalog.from_file(CATALOG_PATH)._configs.values():
        names |= {cfg.name_zh, cfg.name_en, *cfg.names.values()}
    names |= {
        "Louvre",
        "Orsay",
        "Orangerie",
        "Petit Palais",
        "卢浮",
        "羅浮",
        "ルーヴル",
    }
    for lang in LANGS:
        for key, v in COPY[lang].items():
            assert not any(n and n in v for n in names), (lang, key, v)


def test_no_invisible_joiners():
    for lang in LANGS:
        for v in COPY[lang].values():
            assert "⁠" not in v and "​" not in v


def test_t_falls_back_and_formats():
    assert t("ko", "nope-missing") == "nope-missing"
    assert "3" in t("de", "see_all_must_see", n=3)
    assert t("xx", "nav_museums") == COPY["en"]["nav_museums"]


@pytest.mark.parametrize(
    "raw,lang,want",
    [
        ("-140", "en", "140 BC"),
        ("-140", "zh", "公元前140年"),
        ("-140", "ja", "紀元前140年"),
        ("-140", "fr", "140 av. J.-C."),
        (" -140 ", "en", "140 BC"),
        ("1853 vers", "en", "c. 1853"),
        ("1853 vers,1860 tirage", "en", "c. 1853"),
        ("1896 entre,1911 et", "en", "1896–1911"),
        ("1896 entre,1911 et,1931 tirage", "en", "1896–1911"),
        ("1855-1856", "en", "1855–1856"),
        ("1870 avant", "en", "before 1870"),
        ("1870 après", "de", "nach 1870"),
        ("1503", "en", "1503"),
        # 语义模糊的原样留着,和 App 的 formatYear 一致
        ("1867 vers,1868 ou", "en", "1867 vers,1868 ou"),
        ("1870 (?),1871 (?)", "en", "1870 (?),1871 (?)"),
    ],
)
def test_format_year_same_rules_as_app(raw, lang, want):
    from app.services.website.copy import format_year

    assert format_year(raw, lang) == want
