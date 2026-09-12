"""Joconde 属性回填:只补缺、不覆盖、不碰正文。

这三条是脚本存在的前提(见模块头),所以逐条钉死 —— 尤其"不覆盖"和"不碰 sections":
破了前者会冲掉别的源有意的优先级,破了后者会清空 audio_key 让已发布内容变哑。
"""

from scripts.backfill_joconde_attrs import fetch_batch, plan


class _Obj:
    def __init__(self, attributes):
        self.attributes = attributes


ROW = {
    "Reference": "000PE025604",
    "Titre": "La Joconde",
    "Materiaux_techniques": "peinture à l'huile;bois",
    "Mesures": "77 H ; 53 L",
    "Domaine": "peinture",
    "Exposition": None,  # 上游空值
    "Bibliographie": "",  # 上游空串
}


def test_plan_fills_missing_fields():
    add = plan(_Obj({"external_ids": {"P347": "000PE025604"}}), ROW)
    assert add["title_fr"] == "La Joconde"
    assert add["medium_fr"] == "peinture à l'huile;bois"
    assert add["dimensions"] == "77 H ; 53 L"
    assert add["domaine_fr"] == "peinture"


def test_plan_skips_upstream_empty_values():
    """上游 None/空串不该写进去 —— 否则"这个字段查过了但确实没有"和"写了个空"
    在库里长得一样,下次补课会把它当已补齐跳过。"""
    add = plan(_Obj({}), ROW)
    assert "exhibitions_fr" not in add
    assert "bibliography_fr" not in add


def test_plan_never_overwrites_existing_value():
    """已有非空值一律保留:可能来自优先级更高的源(如 Wikidata P186 材质)。"""
    obj = _Obj({"medium_fr": "oil on panel", "dimensions": "77 x 53 cm"})
    add = plan(obj, ROW)
    assert "medium_fr" not in add
    assert "dimensions" not in add
    assert add["title_fr"] == "La Joconde"  # 缺的照补


def test_plan_treats_empty_existing_as_missing():
    add = plan(_Obj({"medium_fr": "", "domaine_fr": None}), ROW)
    assert add["medium_fr"] == "peinture à l'huile;bois"
    assert add["domaine_fr"] == "peinture"


def test_plan_returns_empty_when_nothing_to_add():
    """全都有了 → 空 plan(调用方据此跳过,保证幂等重跑不产生写操作)。"""
    full = {
        "title_fr": "x",
        "medium_fr": "x",
        "dimensions": "x",
        "domaine_fr": "x",
    }
    assert (
        plan(
            _Obj(full),
            {
                k: ROW[k]
                for k in ("Titre", "Materiaux_techniques", "Mesures", "Domaine")
            },
        )
        == {}
    )


def test_plan_only_touches_joconde_keys():
    """不得动 attributes 里的其它键(external_ids/display/extract_* 等)。"""
    from app.services.enrichment.sources.joconde import _FIELD_MAP

    obj = _Obj({"external_ids": {"P347": "x"}, "extract_en": "...", "display": {}})
    add = plan(obj, ROW)
    assert set(add) <= set(_FIELD_MAP)


def test_fetch_batch_keys_by_reference(monkeypatch):
    """批量返回要按 Reference 索引 —— 上游不保证顺序与请求一致,
    按位置对齐会把 A 的材质写到 B 头上。"""
    import scripts.backfill_joconde_attrs as mod

    captured = {}

    def fake_get_json(url, params=None):
        captured["params"] = params
        return {
            "data": [{"Reference": "B", "Titre": "b"}, {"Reference": "A", "Titre": "a"}]
        }

    monkeypatch.setattr(mod, "_get_json", fake_get_json)
    got = fetch_batch("rid-1", ["A", "B"])
    assert got["A"]["Titre"] == "a"
    assert got["B"]["Titre"] == "b"
    assert captured["params"]["Reference__in"] == "A,B"


def test_fetch_batch_drops_unmatched(monkeypatch):
    """上游少返回的 ref 不出现在结果里(调用方据此计未命中,而不是静默补错)。"""
    import scripts.backfill_joconde_attrs as mod

    monkeypatch.setattr(
        mod, "_get_json", lambda url, params=None: {"data": [{"Reference": "A"}]}
    )
    got = fetch_batch("rid-1", ["A", "MISSING"])
    assert set(got) == {"A"}
