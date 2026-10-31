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
