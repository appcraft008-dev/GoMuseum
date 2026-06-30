from app.services.enrichment.category_config import DEFAULT_CATEGORY, category_for


def test_known_qids_map():
    assert category_for("Q3305213") == "painting"
    assert category_for("Q860861") == "sculpture"
    assert category_for("Q125191") == "photograph"


def test_unknown_falls_back():
    assert category_for("Q999999") == DEFAULT_CATEGORY
    assert category_for(None) == DEFAULT_CATEGORY


def test_sections_by_category_and_fallback():
    from app.services.enrichment.category_config import sections_for

    assert sections_for("painting") == [
        "artist",
        "background",
        "analysis",
        "significance",
        "facts",
    ]
    assert sections_for("sculpture")[:2] == ["artist", "material-technique"]
    assert sections_for("unknown") == [
        "background",
        "significance",
        "facts",
    ]


def test_section_label_localized_with_en_fallback():
    from app.services.enrichment.category_config import section_label

    assert section_label("overview", "zh") == "通用描述"
    assert section_label("overview", "en") == "Overview"
    assert section_label("overview", "fr") == "Aperçu"
    assert section_label("overview", "xx") == "Overview"


def test_section_role_has_role_and_length():
    from app.services.enrichment.category_config import section_role

    r = section_role("overview")
    assert "role" in r and "max_chars" in r
    assert r["max_chars"] <= 120  # overview 是短钩子段
    assert section_role("background")["max_chars"] >= 200  # 长故事段


def test_section_role_unknown_falls_back():
    from app.services.enrichment.category_config import section_role

    r = section_role("nonexistent")
    assert "role" in r and "max_chars" in r  # 有兜底，不抛


def test_overview_retired_from_categories():
    from app.services.enrichment.category_config import SECTIONS_BY_CATEGORY

    for codes in SECTIONS_BY_CATEGORY.values():
        assert "overview" not in codes


def test_section_roles_are_distinct_lanes():
    from app.services.enrichment.category_config import section_role

    assert (
        "person" in section_role("artist")["role"].lower()
        or "maker" in section_role("artist")["role"].lower()
    )
    assert (
        "influence" in section_role("significance")["role"].lower()
        or "legacy" in section_role("significance")["role"].lower()
    )
    assert (
        "event" in section_role("background")["role"].lower()
        or "history" in section_role("background")["role"].lower()
    )


def test_guide_target_chars_tiers():
    from app.services.enrichment.category_config import guide_target_chars

    lo, hi = guide_target_chars(5)  # 普通件
    assert (lo, hi) == (270, 420)
    lo2, hi2 = guide_target_chars(50)  # 重点件(>=阈值)
    assert (lo2, hi2) == (420, 675)


def test_section_target_chars_tiers():
    from app.services.enrichment.category_config import section_target_chars

    assert section_target_chars("background", 40) == int(380 * 1.5)  # 570 重点
    assert section_target_chars("background", 10) == 380  # 普通
    assert section_target_chars("background", None) == 380
    assert section_target_chars("facts", 50) == int(200 * 1.5)  # 300


def test_section_roles_base_raised():
    from app.services.enrichment.category_config import SECTION_ROLES

    assert SECTION_ROLES["background"]["max_chars"] == 380
    assert SECTION_ROLES["analysis"]["max_chars"] == 380
    assert SECTION_ROLES["artist"]["max_chars"] == 260
    assert SECTION_ROLES["significance"]["max_chars"] == 240
    assert SECTION_ROLES["facts"]["max_chars"] == 200


def test_analysis_lane_focuses_craft_not_symbols():
    from app.services.enrichment.category_config import section_role

    role = section_role("analysis")["role"].lower()
    assert "craft" in role or "brushwork" in role
    assert "do not re-list" in role or "go beyond" in role or "headline" in role
