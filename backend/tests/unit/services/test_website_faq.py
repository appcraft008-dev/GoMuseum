"""网站问答页内容模型(spec 2026-10-31-website-faq)。"""

import shutil
from datetime import date
from pathlib import Path

import yaml

from app.services.website import faq as F
from app.services.website.faq import (
    Part,
    arrange,
    expiring,
    faq_languages,
    is_stale,
    load_faq,
    validate,
    visible,
)

FIX = Path(__file__).resolve().parents[2] / "fixtures" / "faq"


def _copy(tmp_path) -> Path:
    shutil.copytree(FIX / "demo", tmp_path / "demo")
    return tmp_path


def _edit(root: Path, rel: str, fn):
    p = root / "demo" / rel
    d = yaml.safe_load(p.read_text())
    fn(d)
    p.write_text(yaml.safe_dump(d, allow_unicode=True))


def _load(root):
    F.load_faq.cache_clear()
    return load_faq("demo", root)


def test_demo_loads_and_validates():
    faq = _load(FIX)
    assert faq and validate(faq) == []
    assert faq_languages(faq) == ["en", "fr"]


def test_text_keys_match_structure(tmp_path):
    root = _copy(tmp_path)
    _edit(root, "text/fr.yaml", lambda d: d["items"].pop("booking"))
    errs = validate(_load(root))
    assert any("fr" in e and "booking" in e for e in errs)


def test_per_museum_answer_keys_must_match(tmp_path):
    root = _copy(tmp_path)
    _edit(
        root, "text/fr.yaml", lambda d: d["items"]["closed-days"]["a"].pop("beta_house")
    )
    errs = validate(_load(root))
    assert any("fr" in e and "beta_house" in e for e in errs)


def test_source_and_evidence_required(tmp_path):
    root = _copy(tmp_path)

    def strip(d):
        d["items"][1]["sources"] = []
        d["items"][2]["evidence"] = ""

    _edit(root, "structure.yaml", strip)
    errs = validate(_load(root))
    assert any("booking" in e and "source" in e for e in errs)
    assert any("christmas-new-year" in e and "evidence" in e for e in errs)


def test_placeholder_mismatch(tmp_path):
    root = _copy(tmp_path)

    def drop(d):
        d["items"]["booking"]["q"] = "Faut-il réserver à l'avance ?"

    _edit(root, "text/fr.yaml", drop)
    errs = validate(_load(root))
    assert any("fr" in e and "booking" in e and "alpha" in e for e in errs)


def test_dated_needs_applies_to(tmp_path):
    root = _copy(tmp_path)
    _edit(
        root,
        "text/fr.yaml",
        lambda d: d["items"]["christmas-new-year"].pop("applies_to"),
    )
    errs = validate(_load(root))
    assert any("fr" in e and "applies_to" in e for e in errs)


def test_stale_after_review_by():
    p = Part(None, date(2026, 10, 31), date(2026, 12, 31), ("https://x",), "e")
    assert not is_stale(p, date(2026, 12, 31))
    assert is_stale(p, date(2027, 1, 1))


def test_dated_item_invisible_after_review_by():
    faq = _load(FIX)
    xmas = next(i for i in faq.items if i.id == "christmas-new-year")
    booking = next(i for i in faq.items if i.id == "booking")
    assert visible(xmas, date(2027, 1, 2))
    assert not visible(xmas, date(2027, 1, 3))
    assert visible(booking, date(2030, 1, 1))  # rule 题过期仍显示(带横幅)


def _ids(items):
    return [i.id for i in items]


def test_arrange_pin_window_inclusive():
    faq = _load(FIX)
    pinned, groups = arrange(faq, date(2026, 11, 14))
    assert pinned == [] and "christmas-new-year" in _ids(dict(groups)["holidays"])
    for d in (date(2026, 11, 15), date(2027, 1, 2)):
        pinned, groups = arrange(faq, d)
        assert _ids(pinned) == ["christmas-new-year"]
        assert "holidays" not in dict(groups)  # 空组省略


def test_arrange_keeps_structure_order_and_drops_empty_groups():
    faq = _load(FIX)
    pinned, groups = arrange(faq, date(2027, 1, 3))  # 圣诞题已过期隐藏
    assert pinned == []
    assert [(g, _ids(items)) for g, items in groups] == [
        ("plan", ["closed-days", "booking"])
    ]


def test_expiring_lists_within_days():
    faq = _load(FIX)
    rows = expiring(faq, date(2026, 12, 10), 30)
    assert [(r[0], r[2]) for r in rows] == [("christmas-new-year", date(2027, 1, 2))]
    rows = expiring(faq, date(2027, 1, 1), 30)
    assert [r[0] for r in rows] == [
        "christmas-new-year",
        "closed-days",
        "closed-days",
        "booking",
    ]


def test_unknown_city_returns_none():
    F.load_faq.cache_clear()
    assert load_faq("nowhere", FIX) is None


def test_skipped_museum_counts_as_covered_but_has_no_part(tmp_path):
    root = _copy(tmp_path)

    def skip(d):
        d["items"][0]["per_museum"]["beta_house"] = {"skip": "official site silent"}

    _edit(root, "structure.yaml", skip)
    for lang in ("en", "fr"):
        _edit(
            root,
            f"text/{lang}.yaml",
            lambda d: d["items"]["closed-days"]["a"].pop("beta_house"),
        )
    faq = _load(root)
    item = faq.items[0]
    assert [p.museum for p in item.parts] == ["alpha"]
    assert item.skipped == ("beta_house",)
    assert validate(faq) == []


def test_paris_content_valid():
    F.load_faq.cache_clear()
    faq = load_faq("paris")
    assert faq and validate(faq) == []


def test_per_museum_covers_catalog_city():
    F.load_faq.cache_clear()
    want = set(F.museums_for_city("paris"))
    for item in load_faq("paris").items:
        if item.parts and item.parts[0].museum is None:
            continue
        got = {p.museum for p in item.parts} | set(item.skipped)
        assert want <= got, (item.id, want - got)


def test_paris_has_18_items():
    F.load_faq.cache_clear()
    assert len(load_faq("paris").items) == 18


def test_paris_all_ten_languages():
    F.load_faq.cache_clear()
    assert faq_languages(load_faq("paris")) == list(F.LANGS)


_NUM = __import__("re").compile(r"\d+(?:[:.,]\d+)*")
_MONTHS = "january february march april may june july august september october november december".split()
_WORDS = {"one": 1, "first": 1, "two": 2, "three": 3, "four": 4, "five": 5}
_WORDS |= {"six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10}
# 英文说 ground floor,日韩就是 1 楼
_LOCAL_NUMBERS = {
    ("ja", "bags", "petit_palais"): {"1"},
    ("ko", "bags", "petit_palais"): {"1"},
}


def _nums(text: str) -> set[str]:
    import unicodedata

    return set(_NUM.findall(unicodedata.normalize("NFKC", text)))


def _explained_by_words(en: str) -> set[str]:
    """英文用单词写、译文写成数字的:月份名(12月)和数词(eight → 8)。"""
    words = __import__("re").findall(r"[a-z]+", en.lower())
    out = {str(_MONTHS.index(w) + 1) for w in words if w in _MONTHS}
    return out | {str(_WORDS[w]) for w in words if w in _WORDS}


def _number_errors(got: str, want: str) -> tuple[set[str], set[str]]:
    missing = _nums(want) - _nums(got)
    return missing, _nums(got) - _nums(want) - _explained_by_words(want)


def test_number_check_catches_missing_and_invented():
    want = "Closed on 1 May, open until 18:00 for eight hours."
    assert _number_errors("5月1日闭馆,开到 18:00,共 8 小时。", want) == (set(), set())
    assert _number_errors("6月1日闭馆,开到 18:00,共 8 小时。", want) == (set(), {"6"})
    assert _number_errors("5月1日闭馆,开到 19:00。", want)[0] == {"18:00"}
    assert _number_errors("5月1日闭馆,开到 18:00,门票 €9。", want)[1] == {"9"}


def test_numbers_match_english():
    """译文的数字必须和英文一一对得上:不能少(时间/价格/日期/尺寸),也不能多出错的。"""
    F.load_faq.cache_clear()
    faq = load_faq("paris")
    en = faq.text["en"]["items"]
    for lang, t in faq.text.items():
        for item_id, e in t["items"].items():
            a, ea = e["a"], en[item_id]["a"]
            pairs = (
                [(k, a[k], ea[k]) for k in ea]
                if isinstance(ea, dict)
                else [(None, a, ea)]
            )
            pairs.append(
                (None, e.get("applies_to") or "", en[item_id].get("applies_to") or "")
            )
            pairs.append((None, e["q"], en[item_id]["q"]))
            for k, got, want in pairs:
                missing, extra = _number_errors(got, want)
                extra -= _LOCAL_NUMBERS.get((lang, item_id, k), set())
                assert not missing and not extra, (lang, item_id, k, missing, extra)


def test_name_forms_count_as_the_same_placeholder(tmp_path):
    root = _copy(tmp_path)

    def decline(d):
        d["name_forms"] = {"alpha": {"gen": "Alphy"}}
        d["items"]["booking"]["q"] = d["items"]["booking"]["q"].replace(
            "{alpha}", "{alpha:gen}"
        )

    _edit(root, "text/fr.yaml", decline)
    assert validate(_load(root)) == []


def test_case_placeholder_without_form_is_an_error(tmp_path):
    root = _copy(tmp_path)

    def decline(d):
        d["items"]["booking"]["q"] = d["items"]["booking"]["q"].replace(
            "{alpha}", "{alpha:gen}"
        )

    _edit(root, "text/fr.yaml", decline)
    assert any("{alpha:gen}" in e for e in validate(_load(root)))
