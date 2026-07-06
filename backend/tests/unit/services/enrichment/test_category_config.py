from app.services.enrichment.category_config import DEFAULT_CATEGORY, category_for


def test_known_qids_map():
    # 收录策略:类型归并对齐官方大类,CATEGORY_BY_QID 是单一真相源(加类型=加映射,0代码)
    assert category_for("Q3305213") == "painting"
    assert category_for("Q219423") == "painting"  # 壁画归绘画
    assert category_for("Q860861") == "sculpture"
    assert category_for("Q179700") == "sculpture"  # 雕像
    assert category_for("Q241045") == "sculpture"  # 半身像
    assert category_for("Q1066288") == "sculpture"  # 小像
    assert category_for("Q125191") == "photography"  # 与契约 facet 代码统一
    # 纸上作品(官方 Graphic Arts & Pastels):素描/水彩/色粉/版画/习作/草图
    for q in ("Q93184", "Q18761202", "Q12043905", "Q15123870", "Q2647254", "Q5078274"):
        assert category_for(q) == "works_on_paper"


def test_category_codes_match_contract_facet():
    # 类目代码必须与契约 facet/标签一致(曾有 photograph/decorative 不一致)
    from app.services.enrichment.category_config import SECTIONS_BY_CATEGORY
    from app.services.museum_repo import _CATEGORY_LABELS

    for cat in SECTIONS_BY_CATEGORY:
        assert cat in _CATEGORY_LABELS, f"{cat} 缺 facet 标签"


def test_unknown_falls_back():
    assert category_for("Q999999") == DEFAULT_CATEGORY
    assert category_for(None) == DEFAULT_CATEGORY


def test_sections_by_category_and_fallback():
    from app.services.enrichment.category_config import sections_for

    assert sections_for("painting") == [
        "background",
        "analysis",
        "significance",
        "facts",
    ]
    assert sections_for("sculpture")[0] == "material-technique"
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


def test_artist_not_in_per_work_sections():
    from app.services.enrichment.category_config import SECTIONS_BY_CATEGORY

    for codes in SECTIONS_BY_CATEGORY.values():
        assert "artist" not in codes  # 作者成一等实体,不再是每件的段


def test_polish_added_to_all_static_label_tables():
    # 加语言=加配置验证:pl 必须在所有静态标签表齐全(否则波兰视图混英文)
    from app.services.enrichment.category_config import SECTION_LABELS
    from app.services.enrichment.lang_config import DEFAULT_LANGUAGES, LANG_NAMES
    from app.services.museum_repo import _ALL_LABEL, _CATEGORY_LABELS

    assert "pl" in DEFAULT_LANGUAGES
    assert LANG_NAMES.get("pl") == "Polish"
    assert _ALL_LABEL.get("pl")
    for code, m in _CATEGORY_LABELS.items():
        assert m.get("pl"), f"分类 {code} 缺 pl"
    for code, m in SECTION_LABELS.items():
        assert m.get("pl"), f"段落 {code} 缺 pl"


def test_japanese_added_to_all_static_label_tables():
    from app.services.enrichment.category_config import SECTION_LABELS
    from app.services.enrichment.lang_config import DEFAULT_LANGUAGES, LANG_NAMES
    from app.services.museum_repo import _ALL_LABEL, _CATEGORY_LABELS

    assert "ja" in DEFAULT_LANGUAGES
    assert LANG_NAMES.get("ja") == "Japanese"
    assert _ALL_LABEL.get("ja")
    for code, m in _CATEGORY_LABELS.items():
        assert m.get("ja"), f"分类 {code} 缺 ja"
    for code, m in SECTION_LABELS.items():
        assert m.get("ja"), f"段落 {code} 缺 ja"


def test_korean_added_to_all_static_label_tables():
    from app.services.enrichment.category_config import SECTION_LABELS
    from app.services.enrichment.lang_config import DEFAULT_LANGUAGES, LANG_NAMES
    from app.services.museum_repo import _ALL_LABEL, _CATEGORY_LABELS

    assert "ko" in DEFAULT_LANGUAGES
    assert LANG_NAMES.get("ko") == "Korean"
    assert _ALL_LABEL.get("ko")
    for code, m in _CATEGORY_LABELS.items():
        assert m.get("ko"), f"分类 {code} 缺 ko"
    for code, m in SECTION_LABELS.items():
        assert m.get("ko"), f"段落 {code} 缺 ko"


def test_zh_hant_added_to_all_static_label_tables():
    from app.services.enrichment.category_config import SECTION_LABELS
    from app.services.enrichment.lang_config import DEFAULT_LANGUAGES, LANG_NAMES
    from app.services.museum_repo import _ALL_LABEL, _CATEGORY_LABELS

    assert "zh-hant" in DEFAULT_LANGUAGES
    assert LANG_NAMES.get("zh-hant") == "Traditional Chinese"
    assert _ALL_LABEL.get("zh-hant")
    for code, m in _CATEGORY_LABELS.items():
        assert m.get("zh-hant"), f"分类 {code} 缺 zh-hant"
    for code, m in SECTION_LABELS.items():
        assert m.get("zh-hant"), f"段落 {code} 缺 zh-hant"
