import pytest

from app.services.enrichment.catalog import RANK_LAST, MuseumCatalog, MuseumConfig


def test_get_returns_typed_config():
    cat = MuseumCatalog.from_file("museums.yaml")
    cfg = cat.get("orsay")
    assert isinstance(cfg, MuseumConfig)
    assert cfg.slug == "orsay"
    assert cfg.wikidata_qid == "Q23402"
    assert cfg.sample_size == 30
    assert cfg.sample_qids == []


def test_unknown_slug_raises():
    cat = MuseumCatalog.from_file("museums.yaml")
    with pytest.raises(KeyError):
        cat.get("nope")


def test_categories_and_country_lang_parsed(tmp_path):
    from app.services.enrichment.catalog import MuseumCatalog

    p = tmp_path / "m.yaml"
    p.write_text(
        "museums:\n"
        "  orsay:\n"
        "    name_zh: 奥赛\n    name_en: Orsay\n    city_zh: 巴黎\n    city_en: Paris\n"
        "    country: FR\n    wikidata_qid: Q23402\n    category_filter: Q3305213\n"
        "    categories: [Q3305213, Q860861]\n    country_lang: fr\n"
        "    fetch_limit: 5\n    sample_size: 2\n",
        encoding="utf-8",
    )
    cfg = MuseumCatalog.from_file(p).get("orsay")
    assert cfg.categories == ["Q3305213", "Q860861"]
    assert cfg.country_lang == "fr"


def test_sources_parsed_from_yaml():
    # 上新馆=纯配置:每馆声明自己的补充源(法国馆才有 joconde)
    cfg = MuseumCatalog.from_file("museums.yaml").get("orsay")
    assert cfg.sources == ["joconde", "wikipedia"]


def test_sources_default_to_wikipedia(tmp_path):
    p = tmp_path / "m.yaml"
    p.write_text(
        "museums:\n  x:\n    name_zh: 馆\n    name_en: X\n    city_zh: 城\n"
        "    city_en: C\n    country: NL\n    wikidata_qid: Q1\n"
        "    category_filter: Q3305213\n    fetch_limit: 5\n    sample_size: 2\n",
        encoding="utf-8",
    )
    assert MuseumCatalog.from_file(p).get("x").sources == ["wikipedia"]


def test_categories_defaults_to_category_filter(tmp_path):
    from app.services.enrichment.catalog import MuseumCatalog

    p = tmp_path / "m.yaml"
    p.write_text(
        "museums:\n  orsay:\n    name_zh: 奥赛\n    name_en: Orsay\n    city_zh: 巴黎\n"
        "    city_en: Paris\n    country: FR\n    wikidata_qid: Q23402\n"
        "    category_filter: Q3305213\n    fetch_limit: 5\n    sample_size: 2\n",
        encoding="utf-8",
    )
    cfg = MuseumCatalog.from_file(p).get("orsay")
    assert cfg.categories == ["Q3305213"]
    assert cfg.country_lang is None


def test_orangerie_config_loads():
    # 第二家馆(spec 2026-07-19):纯配置上馆的唯一"代码"
    cat = MuseumCatalog.from_file("museums.yaml")
    cfg = cat.get("orangerie")
    assert cfg.wikidata_qid == "Q726781"
    assert cfg.joconde_museum == "musée de l'Orangerie des Tuileries"
    assert cfg.country_lang == "fr" and "joconde" in cfg.sources


def test_collection_qids_parsed_and_default_empty(tmp_path):
    # 多QID收藏锚点(spec 2026-07-21 louvre):馆身份与收藏锚点分离
    from app.services.enrichment.catalog import MuseumCatalog

    p = tmp_path / "m.yaml"
    p.write_text(
        "museums:\n  louvre:\n    name_zh: 卢浮宫\n    name_en: Louvre\n    city_zh: 巴黎\n"
        "    city_en: Paris\n    country: FR\n    wikidata_qid: Q19675\n"
        "    collection_qids: [Q19675, Q3044768]\n"
        "    category_filter: Q3305213\n    fetch_limit: 5\n    sample_size: 2\n"
        "  orsay:\n    name_zh: 奥赛\n    name_en: Orsay\n    city_zh: 巴黎\n"
        "    city_en: Paris\n    country: FR\n    wikidata_qid: Q23402\n"
        "    category_filter: Q3305213\n    fetch_limit: 5\n    sample_size: 2\n",
        encoding="utf-8",
    )
    cat = MuseumCatalog.from_file(p)
    assert cat.get("louvre").collection_qids == ["Q19675", "Q3044768"]
    assert cat.get("orsay").collection_qids == []  # 不配 → 空(消费方回退单锚点)


def test_louvre_config_loads():
    # 第三家馆(spec 2026-07-21):12部门+馆本体多锚点,无 joconde(v1 不碰 142k)
    cat = MuseumCatalog.from_file("museums.yaml")
    cfg = cat.get("louvre")
    assert cfg.wikidata_qid == "Q19675"
    assert len(cfg.collection_qids) == 13 and "Q3044768" in cfg.collection_qids
    assert cfg.joconde_museum is None and cfg.sources == ["wikipedia"]
    # 百科全书式大馆:整部门全收(古物/装饰艺术 P31 长尾无法逐个列 category)
    assert cfg.collect_all_types is True


def test_collect_all_types_defaults_false(tmp_path):
    # 存量馆(orsay/orangerie)不写此键 → False,保持 category 过滤行为不变
    from app.services.enrichment.catalog import MuseumCatalog

    p = tmp_path / "m.yaml"
    p.write_text(
        "museums:\n  orsay:\n    name_zh: 奥赛\n    name_en: Orsay\n    city_zh: 巴黎\n"
        "    city_en: Paris\n    country: FR\n    wikidata_qid: Q23402\n"
        "    category_filter: Q3305213\n    fetch_limit: 5\n    sample_size: 2\n",
        encoding="utf-8",
    )
    assert MuseumCatalog.from_file(p).get("orsay").collect_all_types is False


def test_rank_parsed_and_defaults_to_last(tmp_path):
    # 探索页馆序:配了按配的来,没配的落末尾(而不是靠 slug 字母序抢到首位)
    p = tmp_path / "m.yaml"
    p.write_text(
        "museums:\n  a:\n    rank: 2\n    name_zh: 甲\n    name_en: A\n    city_zh: 城\n"
        "    city_en: C\n    country: FR\n    wikidata_qid: Q1\n"
        "    category_filter: Q3305213\n    fetch_limit: 5\n    sample_size: 2\n"
        "  b:\n    name_zh: 乙\n    name_en: B\n    city_zh: 城\n"
        "    city_en: C\n    country: FR\n    wikidata_qid: Q2\n"
        "    category_filter: Q3305213\n    fetch_limit: 5\n    sample_size: 2\n",
        encoding="utf-8",
    )
    cat = MuseumCatalog.from_file(p)
    assert cat.get("a").rank == 2
    assert cat.get("b").rank == RANK_LAST


def test_every_museum_has_a_distinct_explicit_rank():
    """上新馆必须显式表态它排第几。

    两道断言各挡一种"顺序没人做过决定"的情形:
    - 漏配 → 落末尾,界面上不显眼,但首位归属其实仍是没人定过的;
    - 撞号 → 同 rank 之间的先后**又退回 slug 字母序**,等于白配。
    """
    items = list(MuseumCatalog.from_file("museums.yaml").items())
    missing = [slug for slug, cfg in items if cfg.rank == RANK_LAST]
    assert not missing, f"这些馆没配 rank: {missing}"
    ranks = [cfg.rank for _, cfg in items]
    assert len(set(ranks)) == len(ranks), f"rank 有重复: {sorted(ranks)}"


def test_names_parsed_and_defaults_to_empty(tmp_path):
    # 馆名其余八语;不配 → 空 dict(消费方回退 name_zh/name_en,老馆零影响)
    p = tmp_path / "m.yaml"
    p.write_text(
        "museums:\n  a:\n    names:\n      fr: Musée A\n      ja: A美術館\n"
        "    name_zh: 甲\n    name_en: A\n    city_zh: 城\n"
        "    city_en: C\n    country: FR\n    wikidata_qid: Q1\n"
        "    category_filter: Q3305213\n    fetch_limit: 5\n    sample_size: 2\n"
        "  b:\n    name_zh: 乙\n    name_en: B\n    city_zh: 城\n"
        "    city_en: C\n    country: FR\n    wikidata_qid: Q2\n"
        "    category_filter: Q3305213\n    fetch_limit: 5\n    sample_size: 2\n",
        encoding="utf-8",
    )
    cat = MuseumCatalog.from_file(p)
    assert cat.get("a").names == {"fr": "Musée A", "ja": "A美術館"}
    assert cat.get("b").names == {}


def test_every_museum_has_all_eight_extra_languages():
    """上新馆必须把八语馆名配齐——漏一门,那门语言的用户看到的是英文名。

    这正是本次报上来的现象:卢浮宫 name_en 是 "Louvre Museum",法语界面
    照搬英文名;而隔壁三个馆的 name_en 恰好是法语拼写,于是看着像
    "只有卢浮宫漏译"。少配一门语言不会报错,只会悄悄回退——所以要这道闸。
    """
    want = {"zh-hant", "fr", "de", "es", "it", "ja", "ko", "pl"}
    for slug, cfg in MuseumCatalog.from_file("museums.yaml").items():
        assert (
            set(cfg.names) == want
        ), f"{slug} 的 names 不全: 缺 {want - set(cfg.names)}"
        # zh/en 不该出现在这里(它们的真相源是 name_zh/name_en,写两处会漂移)
        assert not {"zh", "en"} & set(
            cfg.names
        ), f"{slug}: zh/en 应写在 name_zh/name_en"
