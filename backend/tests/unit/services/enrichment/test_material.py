from app.services.enrichment.material import fetch_object_material
from app.services.enrichment.registry import SourceRegistry
from app.services.enrichment.sources.base import ObjectContribution, Source


class _FakeWiki(Source):
    name = "wikipedia"

    def fetch(self, cfg):
        return []

    def enrich(self, qid, external_ids, context):
        title = (context.get("wiki_titles") or {}).get("en")
        if not title:
            return None
        return ObjectContribution(
            source="wikipedia",
            qid=qid,
            fields={"extract_en": f"lead of {title}"},
            raw={},
        )


def test_fetch_object_material_returns_enrichment_attributes():
    reg = SourceRegistry([_FakeWiki()])
    out = fetch_object_material("Q1", {}, {"en": "The_Balcony"}, reg)
    assert out["extract_en"] == "lead of The_Balcony"
    # 身份/留痕键不进材料
    assert "qid" not in out and "sources" not in out and "external_ids" not in out


def test_fetch_object_material_empty_when_no_contribs():
    reg = SourceRegistry([_FakeWiki()])
    assert fetch_object_material("Q1", {}, {}, reg) == {}


def test_fetch_artist_material_uses_sitelink_titles():
    from app.services.enrichment.material import fetch_artist_material

    seen = {}

    class _Wiki(Source):
        name = "wikipedia"

        def fetch(self, cfg):
            return []

        def enrich(self, qid, ext, ctx):
            seen["titles"] = ctx.get("wiki_titles")
            return ObjectContribution(
                source="wikipedia", qid=qid, fields={"extract_en": "bio"}, raw={}
            )

    calls = []
    out = fetch_artist_material(
        "Q64309678",
        SourceRegistry([_Wiki()]),
        get_entities=_fake_get(calls),
        country_lang="fr",
        artist_qid="Q35548",
    )
    assert seen["titles"] == {"en": "Paul Cézanne", "fr": "Paul Cézanne"}
    assert out == {"artist_extract_en": "bio"}
    assert calls == [(("Q35548",), "sitelinks", ())]


def test_fetch_artist_facts_parses_structured():
    from app.services.enrichment.material import _artist_facts_from_rows

    def fake(sparql):
        return [
            {
                "birth": {"value": "1832-01-23T00:00:00Z"},
                "death": {"value": "1883-04-30T00:00:00Z"},
                "natLabel": {"value": "France"},
                "workLabel": {"value": "Olympia"},
            },
            {"natLabel": {"value": "France"}, "workLabel": {"value": "The Fifer"}},
            {"natLabel": {"value": "France"}, "workLabel": {"value": "Olympia"}},
        ]

    f = _artist_facts_from_rows(fake(None))
    assert f["artist_birth"] == "1832" and f["artist_death"] == "1883"
    assert f["artist_nationality"] == "France"
    assert f["artist_notable_works"] == ["Olympia", "The Fifer"]  # 去重保序


def test_fetch_artist_facts_empty_on_no_rows():
    from app.services.enrichment.material import _artist_facts_from_rows

    assert _artist_facts_from_rows([]) == {}


def test_fetch_artist_facts_skips_raw_qid_works():
    from app.services.enrichment.material import _artist_facts_from_rows

    def fake(sparql):
        return [
            {"workLabel": {"value": "Homage to Cézanne"}},
            {"workLabel": {"value": "Q17490760"}},  # 无标签→跳
            {"natLabel": {"value": "France"}},
        ]

    f = _artist_facts_from_rows(fake(None))
    assert f["artist_notable_works"] == ["Homage to Cézanne"]  # QID 被过滤
    assert f["artist_nationality"] == "France"


def test_fetch_wikidata_labels():
    from app.services.enrichment.material import _labels_from_rows

    def fake(sparql):
        return [
            {"l": {"value": "La Nuit étoilée", "xml:lang": "fr"}},
            {"l": {"value": "Starry Night", "xml:lang": "en"}},
        ]

    out = _labels_from_rows(fake(None), ["en", "fr", "de"])
    assert out == {"fr": "La Nuit étoilée", "en": "Starry Night"}  # 只含 Wikidata 有的


def test_fetch_artist_i18n_facts_multilang_labels():
    # 作者国籍(P27)/代表作(P800)的多语权威标签(交接③:非英语界面显英文)
    from app.services.enrichment.material import _artist_i18n_from_rows

    W = {"value": "http://www.wikidata.org/entity/Q622062"}
    rows = [
        {
            "natLabel": {"value": "法国", "xml:lang": "zh"},
            "work": W,
            "workLabel": {"value": "奥林匹亚", "xml:lang": "zh"},
        },
        {
            "natLabel": {"value": "France", "xml:lang": "en"},
            "work": W,
            "workLabel": {"value": "Olympia", "xml:lang": "en"},
        },
        {
            "natLabel": {"value": "Frankreich", "xml:lang": "de"},
            "work": W,
            "workLabel": {"value": "Olympia", "xml:lang": "de"},
        },
    ]
    out = _artist_i18n_from_rows(rows, ["zh", "en", "de"])
    assert out["nationality_i18n"] == {"zh": "法国", "en": "France", "de": "Frankreich"}
    assert out["notable_works_i18n"]["zh"] == ["奥林匹亚"]
    assert out["notable_works_i18n"]["en"] == ["Olympia"]


def test_fetch_artist_i18n_facts_skips_raw_qids_and_empty():
    from app.services.enrichment.material import _artist_i18n_from_rows

    rows = [
        {"natLabel": {"value": "Q142", "xml:lang": "zh"}},  # 无标签退回QID→跳过
        {
            "work": {"value": "http://www.wikidata.org/entity/Q622062"},
            "workLabel": {"value": "Olympia", "xml:lang": "en"},
        },
    ]
    out = _artist_i18n_from_rows(rows, ["zh", "en"])
    assert "zh" not in out["nationality_i18n"]
    assert out["notable_works_i18n"]["en"] == ["Olympia"]
    # 中文没有权威标签 → 回退英文,而不是整条缺席:各语言列的必须是同一批作品
    assert out["notable_works_i18n"]["zh"] == ["Olympia"]


def test_fetch_labels_prefers_zh_hans_over_traditional():
    # 繁简混杂尾巴:Wikidata zh 标签变体不定(愛德華·馬奈)→ zh-hans > zh-cn > zh
    from app.services.enrichment.material import _labels_from_rows

    rows = [
        {"l": {"value": "愛德華·馬奈", "xml:lang": "zh"}},
        {"l": {"value": "爱德华·马奈", "xml:lang": "zh-hans"}},
        {"l": {"value": "Édouard Manet", "xml:lang": "fr"}},
    ]
    out = _labels_from_rows(rows, ["zh", "fr"])
    assert out["zh"] == "爱德华·马奈"  # hans 优先于繁体 zh
    assert out["fr"] == "Édouard Manet"


def test_fetch_labels_zh_falls_back_when_no_hans():
    from app.services.enrichment.material import _labels_from_rows

    rows = [{"l": {"value": "馬奈", "xml:lang": "zh"}}]
    out = _labels_from_rows(rows, ["zh"])
    assert out["zh"] == "马奈"  # 没 hans 时取 zh 并 t2s 转简


def test_zh_label_converted_to_simplified_when_only_traditional():
    # 根因:马奈/高更等在 Wikidata 只有繁体 zh 标签(无 zh-hans)→ OpenCC t2s 确定性转换
    from app.services.enrichment.material import _labels_from_rows

    rows = [{"l": {"value": "愛德華·馬奈", "xml:lang": "zh"}}]
    out = _labels_from_rows(rows, ["zh"])
    assert out["zh"] == "爱德华·马奈"  # 繁→简


def test_zh_hans_label_untouched():
    from app.services.enrichment.material import _labels_from_rows

    rows = [{"l": {"value": "克劳德·莫奈", "xml:lang": "zh-hans"}}]
    out = _labels_from_rows(rows, ["zh"])
    assert out["zh"] == "克劳德·莫奈"


def test_artist_i18n_facts_zh_converted():
    from app.services.enrichment.material import _artist_i18n_from_rows

    rows = [
        {"natLabel": {"value": "法國", "xml:lang": "zh"}},
        {
            "work": {"value": "http://www.wikidata.org/entity/Q622062"},
            "workLabel": {"value": "奧林匹亞", "xml:lang": "zh"},
        },
    ]
    out = _artist_i18n_from_rows(rows, ["zh"])
    assert out["nationality_i18n"]["zh"] == "法国"
    assert out["notable_works_i18n"]["zh"] == ["奥林匹亚"]


def test_zh_hant_prefers_traditional_authoritative_label():
    from app.services.enrichment.material import _labels_from_rows

    rows = [
        {"l": {"value": "顯現", "xml:lang": "zh-hant"}},
        {"l": {"value": "显现", "xml:lang": "zh-hans"}},
    ]
    out = _labels_from_rows(rows, ["zh-hant"])
    assert out["zh-hant"] == "顯現"  # 权威繁体优先


def test_zh_hant_converts_simplified_to_traditional_when_only_hans():
    from app.services.enrichment.material import _labels_from_rows

    rows = [{"l": {"value": "爱德华·马奈", "xml:lang": "zh-hans"}}]
    out = _labels_from_rows(rows, ["zh-hant"])
    assert out["zh-hant"] == "愛德華·馬奈"  # 简→繁 s2t


def test_zh_hant_prefers_mandarin_over_cantonese_hk_label():
    """zh-hk 是粤语拼读的另一套音译传统,不能压过 zh 转繁。

    实测 Q35548 Cézanne:Wikidata 无 zh-hant/zh-tw 标签,zh-hk 标签是「保羅·施傘」,
    旧回退序取到它,于是每一段繁体讲解都把塞尚叫成施傘(污染 27 段)。
    """
    from app.services.enrichment.material import _labels_from_rows

    rows = [
        {"l": {"value": "保羅·施傘", "xml:lang": "zh-hk"}},
        {"l": {"value": "保罗·塞尚", "xml:lang": "zh"}},
    ]
    out = _labels_from_rows(rows, ["zh-hant"])
    assert out["zh-hant"] == "保羅·塞尚"


def test_zh_hant_still_uses_hk_label_as_last_resort():
    """但 zh-hk 仍留在链尾:它是唯一的中文标签时,人工标签好过机翻兜底。"""
    from app.services.enrichment.material import _labels_from_rows

    rows = [{"l": {"value": "梵高", "xml:lang": "zh-hk"}}]
    out = _labels_from_rows(rows, ["zh-hant"])
    assert out["zh-hant"] == "梵高"


def test_zh_still_simplified_regression():
    from app.services.enrichment.material import _labels_from_rows

    rows = [{"l": {"value": "愛德華·馬奈", "xml:lang": "zh"}}]
    out = _labels_from_rows(rows, ["zh"])
    assert out["zh"] == "爱德华·马奈"  # 繁→简,回归不破


def test_non_variant_language_not_converted():
    from app.services.enrichment.material import _labels_from_rows

    rows = [{"l": {"value": "エドゥアール・マネ", "xml:lang": "ja"}}]
    out = _labels_from_rows(rows, ["ja"])
    assert out["ja"] == "エドゥアール・マネ"  # 非变体不动


def test_fetch_museum_intro_material_sitelink_then_extract():
    from app.services.enrichment.material import fetch_museum_intro_material

    calls = []

    def fake_get_json(url, params):
        calls.append(url)
        if "wikidata" in url:
            return {
                "entities": {
                    "Q23402": {"sitelinks": {"enwiki": {"title": "Musée d'Orsay"}}}
                }
            }
        return {"query": {"pages": {"1": {"extract": "The Musée d'Orsay is..."}}}}

    out = fetch_museum_intro_material("Q23402", get_json=fake_get_json)
    assert out["extract_en"].startswith("The Musée d'Orsay")
    assert any("wikidata" in u for u in calls) and any("wikipedia" in u for u in calls)


def test_fetch_museum_intro_material_no_sitelink():
    from app.services.enrichment.material import fetch_museum_intro_material

    out = fetch_museum_intro_material(
        "Q1", get_json=lambda u, p: {"entities": {"Q1": {"sitelinks": {}}}}
    )
    assert out["extract_en"] is None


def test_fetch_labels_batch_matches_single_semantics():
    """批量版必须与单件版逐字同义(含 zh 变体收敛),只是网络往返少了 N 倍。"""
    from app.services.enrichment.material import (
        _labels_from_rows,
        fetch_wikidata_labels_batch,
    )

    def _row(q, lang, val):
        return {
            "item": {"value": f"http://www.wikidata.org/entity/{q}"},
            "l": {"xml:lang": lang, "value": val},
        }

    rows = [
        _row("Q12418", "en", "Mona Lisa"),
        _row("Q12418", "zh-hans", "蒙娜丽莎"),  # 变体应收敛到 zh
        _row("Q762", "en", "Leonardo"),
    ]
    batch = fetch_wikidata_labels_batch(
        ["Q12418", "Q762"], ["en", "zh"], run_query=lambda s: rows
    )
    assert batch["Q12418"] == {"en": "Mona Lisa", "zh": "蒙娜丽莎"}
    assert batch["Q762"] == {"en": "Leonardo"}

    single = _labels_from_rows(
        [
            {"l": {"xml:lang": "en", "value": "Mona Lisa"}},
            {"l": {"xml:lang": "zh-hans", "value": "蒙娜丽莎"}},
        ],
        ["en", "zh"],
    )
    assert single == batch["Q12418"]  # 语义一致


def test_fetch_labels_batch_chunks_and_skips_non_wikidata():
    from app.services.enrichment import material as mat

    calls = []

    def fake(sparql):
        calls.append(sparql)
        return []

    qids = [f"Q{i}" for i in range(450)] + ["joconde-000SC010033"]
    mat.fetch_wikidata_labels_batch(qids, ["en"], run_query=fake)
    assert len(calls) == 3  # 450/200 → 3 批
    assert "joconde" not in "".join(calls)  # 合成把手不进 SPARQL


def test_fetch_labels_batch_survives_failed_chunk(monkeypatch):
    """单批失败重试一次仍败 → 跳过该批,不炸全局(幂等重跑再补)。"""
    import time as _t

    from app.services.enrichment import material as mat

    monkeypatch.setattr(_t, "sleep", lambda s: None)  # material 内是函数级 import
    state = {"n": 0}

    def flaky(sparql):
        state["n"] += 1
        if state["n"] <= 2:  # 第一批的两次尝试都失败
            raise RuntimeError("WDQS down")
        return [
            {
                "item": {"value": "http://www.wikidata.org/entity/Q300"},
                "l": {"xml:lang": "en", "value": "OK"},
            }
        ]

    out = mat.fetch_wikidata_labels_batch(
        [f"Q{i}" for i in range(250)], ["en"], run_query=flaky
    )
    assert out == {"Q300": {"en": "OK"}}  # 第二批的结果仍拿到


def test_one_failing_source_does_not_kill_the_item():
    """纪律①:单源失败跳过继续。此前任一源抛异常会炸掉整个 generate 运行——
    2026-07-27 实测 Joconde 返回非 JSON 使 orsay/orangerie 预热两次全崩,
    而只用 wikipedia 的 louvre 完好。"""
    from app.services.enrichment.material import fetch_object_material

    class _Boom:
        name = "joconde"

        def enrich(self, qid, ext, ctx):
            raise RuntimeError("Joconde 返回非 JSON")

    class _Good:
        name = "wikipedia"

        def enrich(self, qid, ext, ctx):
            from app.services.enrichment.sources.base import ObjectContribution

            return ObjectContribution(
                source="wikipedia", qid=qid, raw={}, fields={"summary": "ok"}
            )

    class _Reg:
        def route(self, ext):
            return [_Boom(), _Good()]

    out = fetch_object_material("Q1", {}, {}, _Reg())
    assert isinstance(out, dict)  # 没抛异常,坏源被跳过


def test_all_sources_failing_returns_empty_not_raise():
    from app.services.enrichment.material import fetch_object_material

    class _Boom:
        name = "x"

        def enrich(self, qid, ext, ctx):
            raise RuntimeError("down")

    class _Reg:
        def route(self, ext):
            return [_Boom()]

    assert fetch_object_material("Q1", {}, {}, _Reg()) == {}


# ── 代表作:各语言必须列同一批作品(用户 2026-09-01 反馈) ────────────────────
def _work(n):
    return {"value": f"http://www.wikidata.org/entity/Q{n}"}


def _rows_uneven():
    """5 件作品,标签覆盖故意不均 —— 复刻莫迪利亚尼实况:
    en 全有、zh 只有 1 件、ja 2 件。行序打乱,证明选集与行序无关。"""
    rows = []
    for i, n in enumerate([101, 102, 103, 104, 105]):
        rows.append(
            {"work": _work(n), "workLabel": {"value": f"W{i}-en", "xml:lang": "en"}}
        )
    rows.append({"work": _work(103), "workLabel": {"value": "W2-zh", "xml:lang": "zh"}})
    rows.append({"work": _work(101), "workLabel": {"value": "W0-ja", "xml:lang": "ja"}})
    rows.append({"work": _work(105), "workLabel": {"value": "W4-ja", "xml:lang": "ja"}})
    return rows


def test_notable_works_same_set_across_languages():
    """旧实现每语言各自 append 再各自 [:5] → zh 只有 1 条、ja 2 条、en 5 条,
    而且三者根本不是同一批画。新实现:先定作品集合,再逐语言取标签。"""
    from app.services.enrichment.material import _artist_i18n_from_rows

    langs = ["en", "zh", "ja"]
    out = _artist_i18n_from_rows(_rows_uneven(), langs)
    w = out["notable_works_i18n"]
    assert {len(w[x]) for x in langs} == {
        5
    }, f"各语言长度必须一致,实得 { {x: len(w[x]) for x in langs} }"
    # 第 i 位在各语言里指的是同一件作品(标签前缀相同) —— 这是本条测试的要害
    for i in range(5):
        assert (
            len({w[x][i].split("-")[0] for x in langs}) == 1
        ), f"第 {i} 位跨语言不是同一件"
    # 顺序由"标签覆盖度"决定:有两个语言标注的(W0/W2/W4)排在只有 en 的(W1/W3)之前
    assert [v.split("-")[0] for v in w["en"]] == ["W0", "W2", "W4", "W1", "W3"]
    # 有权威标签的用本地化,没有的回退英文 —— 而不是整件缺席
    assert w["zh"] == ["W0-en", "W2-zh", "W4-en", "W1-en", "W3-en"]
    assert w["ja"] == ["W0-ja", "W2-en", "W4-ja", "W1-en", "W3-en"]


def test_notable_works_selection_is_language_order_independent():
    """选集判据必须与传入语言的顺序/行序无关,否则又回到"各挑各的"。"""
    from app.services.enrichment.material import _artist_i18n_from_rows

    rows = _rows_uneven()
    a = _artist_i18n_from_rows(rows, ["en", "zh", "ja"])
    b = _artist_i18n_from_rows(list(reversed(rows)), ["ja", "en", "zh"])
    assert a["notable_works_i18n"]["en"] == b["notable_works_i18n"]["en"]


def test_notable_works_caps_at_five_by_label_coverage():
    """超过 5 件时,按"被标注得最全"取前 5(近似最知名),同分按 qid 稳定排。"""
    from app.services.enrichment.material import _artist_i18n_from_rows

    rows = []
    for n in range(201, 208):  # 7 件,en 都有
        rows.append(
            {"work": _work(n), "workLabel": {"value": f"Q{n}-en", "xml:lang": "en"}}
        )
    for n in (207, 206):  # 这两件另有中文标签 → 覆盖度更高,应排最前
        rows.append(
            {"work": _work(n), "workLabel": {"value": f"Q{n}-zh", "xml:lang": "zh"}}
        )
    out = _artist_i18n_from_rows(rows, ["en", "zh"])
    got = out["notable_works_i18n"]["en"]
    assert len(got) == 5
    assert got[:2] == ["Q206-en", "Q207-en"], got  # 覆盖度 2 的排前,同分按 qid


def test_notable_works_zh_hant_converts_from_zh_not_english():
    """繁体没有权威标签时应走简体转繁(字形变体,确定性),而不是掉到英文。"""
    from app.services.enrichment.material import _artist_i18n_from_rows

    rows = [
        {"work": _work(301), "workLabel": {"value": "Olympia", "xml:lang": "en"}},
        {"work": _work(301), "workLabel": {"value": "奥林匹亚", "xml:lang": "zh"}},
    ]
    out = _artist_i18n_from_rows(rows, ["en", "zh-hant"])
    assert out["notable_works_i18n"]["zh-hant"] == ["奧林匹亞"]


def _creator_row(aq, rank="NormalRank", cert=None, refs=0, var="artist"):
    r = {
        var: {"value": f"http://www.wikidata.org/entity/{aq}"},
        "rank": {"value": f"http://wikiba.se/ontology#{rank}"},
        "refs": {"value": str(refs)},
    }
    if cert:
        r["cert"] = {"value": f"http://www.wikidata.org/entity/{cert}"}
    return r


# 真实形状:橘园 Q64309678《静物,梨和青苹果》—— 塞尚(presumably,引用=橘园官网)
# 与加歇医生(possibly,零引用)同挂 P170。旧代码"取首个"把加歇的传记灌进了
# artist_extract_*,10 语 78 条正文全在讲梵高的医生画了这幅静物。
_Q64309678 = [
    _creator_row("Q35548", cert="Q18122778", refs=1),  # Cézanne, presumably
    _creator_row("Q1369513", cert="Q30230067", refs=0),  # Gachet, possibly
]


def test_resolve_creator_prefers_better_sourced_claim():
    from app.services.enrichment.material import _creator_from_rows

    assert _creator_from_rows(_Q64309678) == "Q35548"
    # 行序不该影响结果 —— SPARQL 不保证顺序,这正是旧代码的病根
    assert _creator_from_rows(_Q64309678[::-1]) == "Q35548"


def test_resolve_creator_rank_beats_qualifier():
    from app.services.enrichment.material import _creator_from_rows

    rows = [
        _creator_row("Q1", cert="Q30230067", rank="PreferredRank"),
        _creator_row("Q2", refs=9),  # 无限定 + 多引用,但只是 normal rank
    ]
    assert _creator_from_rows(rows) == "Q1"


def test_resolve_creator_skips_blank_node_and_deprecated():
    from app.services.enrichment.material import _creator_from_rows

    rows = [
        {
            "artist": {"value": "http://www.wikidata.org/.well-known/genid/abc123"},
            "rank": {"value": "http://wikiba.se/ontology#NormalRank"},
        },
        _creator_row("Q7", rank="DeprecatedRank"),
    ]
    assert _creator_from_rows(rows) is None


def test_fetch_creators_batch_picks_same_winner_as_single():
    """批量路径与单件路径必须给出同一个人 —— 两把尺子就是本 bug 的翻版。"""
    from app.services.enrichment.backfill import _fetch_creators

    rows = [
        dict(r, item={"value": "http://www.wikidata.org/entity/Q64309678"})
        for r in (
            _creator_row("Q35548", cert="Q18122778", refs=1, var="creator"),
            _creator_row("Q1369513", cert="Q30230067", var="creator"),
        )
    ]
    assert _fetch_creators(["Q64309678"], run_query=lambda s: rows[::-1]) == {
        "Q64309678": "Q35548"
    }


def test_has_qualifier_marker_detects_real_disclaimer_phrases():
    from app.services.enrichment.material import _has_qualifier_marker

    # 真实 Joconde 数据(2026-10-07 实测奥赛+橘园 Auteur 字段):这些都是
    # "这不是作者本人画的"类表述,必须命中。
    assert _has_qualifier_marker("anonyme;VAN GOGH Vincent (d'après)") is True
    assert _has_qualifier_marker("Cézanne Paul (1839-1906) (attribué à)") is True
    assert _has_qualifier_marker("Boucher François (d'après)") is True
    assert _has_qualifier_marker("CLOUET François (atelier)") is True
    assert _has_qualifier_marker("Courbet Gustave (genre de);anonyme") is True
    assert _has_qualifier_marker("anonyme") is True
    assert (
        _has_qualifier_marker("SEGUIN Armand;Gauguin Paul (attribution incertaine)")
        is True
    )
    # 大小写不敏感(Joconde 惯用全大写姓氏段落,限定词有时跟着一起大写)
    assert _has_qualifier_marker("BOUCHER FRANÇOIS (D'APRÈS)") is True
    # 别名标记(dit/née)和工匠角色词(fondeur)不是弃权信号,不该命中——
    # 这些交给拆分+解析步骤正常处理(spec §3.2 步骤0的说明)。
    assert (
        _has_qualifier_marker("BENJAMIN-CONSTANT (dit);CONSTANT Jean Joseph Benjamin")
        is False
    )
    assert _has_qualifier_marker("ALLAR André Joseph;MATIFA C (fondeur)") is False
    assert (
        _has_qualifier_marker(
            "BESNARD Charlotte Gabrielle;DUBRAY Charlotte Gabrielle (née)"
        )
        is False
    )
    # 正常署名,无限定词
    assert _has_qualifier_marker("SOUTINE Chaïm") is False
    assert _has_qualifier_marker("RENOIR Pierre Auguste") is False


def test_reorder_candidates_tries_every_split_point():
    from app.services.enrichment.material import _reorder_candidates

    # 两个词:只有一种切法(k=1)
    assert _reorder_candidates("SOUTINE Chaïm") == ["Chaïm SOUTINE"]
    # 多词姓氏(真实橘园数据,4个词)——断言**全部** n-1=3 种切法的完整列表,
    # 不是只断言"其中一条在不在里面"(只查子串的话,一个只实现了 k=1、
    # 对 k≥2 吐垂圾的版本也能让"in"断言通过,见全分支审阅 Important #4)。
    # 真实案例(2026-10-07 实测):"CONSTANT Jean Joseph Benjamin"真正能命中
    # Wikidata 的切法正是 k=1("Jean Joseph Benjamin CONSTANT")。
    assert _reorder_candidates("CONSTANT Jean Joseph Benjamin") == [
        "Jean Joseph Benjamin CONSTANT",
        "Joseph Benjamin CONSTANT Jean",
        "Benjamin CONSTANT Jean Joseph",
    ]
    # 另一个真实多词姓氏案例,交叉验证不是只对上面那一个输入凑巧对
    assert _reorder_candidates("DE MACHY Pierre Antoine") == [
        "MACHY Pierre Antoine DE",
        "Pierre Antoine DE MACHY",
        "Antoine DE MACHY Pierre",
    ]
    # 单个词:没有可重排的,返回空列表
    assert _reorder_candidates("Anonyme") == []
    assert _reorder_candidates("") == []


def test_segment_candidates_filters_by_exact_word_match():
    from app.services.enrichment.material import _segment_candidates
    from app.services.matching.normalize import normalize, tokens

    # 真实案例(2026-10-07 实测):"LEON Paul"会前缀匹配到 Léon-Paul Fargue
    # (法国诗人),match.text 是"Léon-Paul Fargue",归一化后的词集合是
    # {leon, paul, fargue},和输入词集合 {leon, paul} 不相等——必须被滤掉。
    def fake_search(text, *, limit=5):
        return [
            {
                "id": "Q599801",
                "label": "Léon-Paul Fargue",
                "match": {"type": "label", "text": "Léon-Paul Fargue"},
            },
        ]

    word_set = frozenset(tokens(normalize("LEON Paul")))
    assert (
        _segment_candidates("LEON Paul", search_entities=fake_search, word_set=word_set)
        == []
    )

    # 词集合精确相等的候选要保留
    def fake_search_exact(text, *, limit=5):
        return [
            {
                "id": "Q160141",
                "label": "Chaïm Soutine",
                "match": {"type": "label", "text": "Chaïm Soutine"},
            },
        ]

    word_set2 = frozenset(tokens(normalize("Chaïm Soutine")))
    assert _segment_candidates(
        "SOUTINE Chaïm", search_entities=fake_search_exact, word_set=word_set2
    ) == ["Q160141"]

    # match 字段缺失时退回用 label 比较,不能抛异常(Review Focus 第3条)
    def fake_search_no_match(text, *, limit=5):
        return [{"id": "Q1", "label": "Chaïm Soutine"}]

    assert _segment_candidates(
        "SOUTINE Chaïm", search_entities=fake_search_no_match, word_set=word_set2
    ) == ["Q1"]

    # 原始顺序+重排都会被尝试,两次查询结果去重合并——注意重排只调换词的
    # 位置,不改每个词自身的大小写(_reorder_candidates 的实现就是这样),
    # 所以"SOUTINE Chaïm"重排后是"Chaïm SOUTINE"(SOUTINE 仍大写),不是
    # "Chaïm Soutine"(这个大小写写法实测跑过一遍脚本才发现:写成后者会让
    # 两次查询的 text 都对不上,fake 函数永远返回空,测试会静默测不出东西
    # 而不是报错——写 fake 查询函数时务必核对 _reorder_candidates 真实
    # 产出的字符串,不要凭感觉拼大小写)。
    calls = []

    def fake_search_both_orders(text, *, limit=5):
        calls.append(text)
        if text == "Chaïm SOUTINE":
            return [
                {
                    "id": "Q160141",
                    "label": "Chaïm Soutine",
                    "match": {"text": "Chaïm Soutine"},
                }
            ]
        return []

    result = _segment_candidates(
        "SOUTINE Chaïm", search_entities=fake_search_both_orders, word_set=word_set2
    )
    assert result == ["Q160141"]
    assert "SOUTINE Chaïm" in calls  # 原始顺序查过
    assert "Chaïm SOUTINE" in calls  # 重排后也查过(注意大小写:SOUTINE 仍大写)


def test_resolve_creator_by_name_real_unambiguous_artists():
    """2026-10-07 橘园 TOP50 内容复核手工核实过的 7 个真实作者,mock HTTP
    响应固定,离线跑,必须原样复现这 7 个 qid。

    ⚠️ `match.text` 必须填**真实会返回的那个字符串**,不能图省事填 Wikidata
    的 canonical label——写这份计划时实测过 Modigliani 这一条,拿 canonical
    label "Amedeo Modigliani" 当 match.text 会让词集合精确匹配(spec §3.2
    步骤2)误判失败(因为 Joconde 原串拼的是"Amadeo",跟"Amedeo"差一个
    字母),而真实 Wikidata 搜索返回的 match.text 是**别名**"Amadeo
    Modigliani"(与 Joconde 原串完全一致),所以 Modigliani 这一条的
    match_text 和前面几条的 label 不一样,是故意的,不是打错字。"""
    from app.services.enrichment.material import resolve_creator_by_name

    def make_search(qid, match_text):
        def _search(text, *, limit=5):
            return [{"id": qid, "label": match_text, "match": {"text": match_text}}]

        return _search

    def make_claims(qid):
        def _claims(qids):
            return {
                qid: {
                    "claims": {
                        "P31": [{"mainsnak": {"datavalue": {"value": {"id": "Q5"}}}}],
                        "P106": [
                            {"mainsnak": {"datavalue": {"value": {"id": "Q1028181"}}}}
                        ],
                    }
                }
            }

        return _claims

    cases = [
        ("Renoir Pierre Auguste", "Q39931", "Pierre-Auguste Renoir"),
        ("SOUTINE Chaïm", "Q160141", "Chaïm Soutine"),
        ("DERAIN André", "Q156272", "André Derain"),
        ("UTRILLO Maurice", "Q108301", "Maurice Utrillo"),
        ("Matisse Henri", "Q5589", "Henri Matisse"),
        ("ROUSSEAU Henri;LE DOUANIER ROUSSEAU", "Q156386", "Henri Rousseau"),
        # match_text 是别名"Amadeo Modigliani",不是 canonical label——见上面的说明
        ("Modigliani Amadeo", "Q120993", "Amadeo Modigliani"),
    ]
    for raw_name, expected_qid, match_text in cases:
        got = resolve_creator_by_name(
            raw_name,
            search_entities=make_search(expected_qid, match_text),
            get_claims=make_claims(expected_qid),
        )
        assert (
            got == expected_qid
        ), f"{raw_name!r} 应该解析成 {expected_qid},实际是 {got!r}"


def test_resolve_creator_by_name_abstains_on_known_ambiguous_cases():
    from app.services.enrichment.material import resolve_creator_by_name

    # 真实限定词案例:整串命中"d'après"直接弃权,不会拆分后把
    # "VAN GOGH Vincent"单独解析成功再误采信(真实 Joconde 署名)。
    def search_should_not_be_called(text, *, limit=5):
        raise AssertionError(f"限定词弃权应该在拆分前拦住,不该查询 {text!r}")

    assert (
        resolve_creator_by_name(
            "anonyme;VAN GOGH Vincent (d'après)",
            search_entities=search_should_not_be_called,
        )
        is None
    )

    # Cézanne 父子同名同职业撞车:职业过滤后剩两个人,必须弃权。
    def search_cezanne(text, *, limit=5):
        return [
            {
                "id": "Q35548",
                "label": "Paul Cézanne",
                "match": {"text": "Paul Cézanne"},
            },
            {
                "id": "Q17277915",
                "label": "Paul Cézanne",
                "match": {"text": "Paul Cézanne"},
            },
        ]

    def claims_both_painters(qids):
        return {
            qid: {
                "claims": {
                    "P31": [{"mainsnak": {"datavalue": {"value": {"id": "Q5"}}}}],
                    "P106": [
                        {"mainsnak": {"datavalue": {"value": {"id": "Q1028181"}}}}
                    ],
                }
            }
            for qid in qids
        }

    assert (
        resolve_creator_by_name(
            "Cézanne Paul",
            search_entities=search_cezanne,
            get_claims=claims_both_painters,
        )
        is None
    )

    # 空/退化输入不能崩,必须返回 None(Review Focus 第4条)
    assert resolve_creator_by_name(None) is None
    assert resolve_creator_by_name("") is None
    assert resolve_creator_by_name("   ") is None
    assert resolve_creator_by_name(";") is None


def test_resolve_creator_by_name_handles_real_multi_segment_signature():
    """真实奥赛署名"BENJAMIN-CONSTANT (dit);CONSTANT Jean Joseph Benjamin"
    (画家 Jean-Joseph Benjamin-Constant 的艺名+本名两段)。第一段带着
    "(dit)"文本直接查,搜不到任何候选(0 个);第二段重排后能命中。跨段裁决:
    一段失败(忽略)+一段成功 -> 集合大小为1 -> 采信。"""
    from app.services.enrichment.material import resolve_creator_by_name

    def search(text, *, limit=5):
        if text == "Jean Joseph Benjamin CONSTANT":
            return [
                {
                    "id": "Q968357",
                    "label": "Jean-Joseph Benjamin-Constant",
                    "match": {"text": "Jean-Joseph Benjamin-Constant"},
                }
            ]
        return []  # 其它查询(含"BENJAMIN-CONSTANT (dit)"原串)都搜不到

    def claims(qids):
        return {
            qid: {
                "claims": {
                    "P31": [{"mainsnak": {"datavalue": {"value": {"id": "Q5"}}}}],
                    "P106": [
                        {"mainsnak": {"datavalue": {"value": {"id": "Q1028181"}}}}
                    ],
                }
            }
            for qid in qids
        }

    got = resolve_creator_by_name(
        "BENJAMIN-CONSTANT (dit);CONSTANT Jean Joseph Benjamin",
        search_entities=search,
        get_claims=claims,
    )
    assert got == "Q968357"


def test_resolve_creator_by_name_does_not_misattribute_leon_paul():
    """2026-10-07 全分支审阅发现的真实回归(已核实,不是假设):commit eb5b0758
    往白名单加了 photographer/architect 想救 Vacquerie/Coquart,但同一条改动
    把"LEON Paul"从"0 候选弃权"变成"1 个候选、误判成委内瑞拉记者 Paul León
    (Q128960542,P106 恰好含 photographer)"——真实 Wikidata 候选集(curl 核实
    过):Q115793023(无职业)、Q3371732(P106=professor)、Q128960542(P106 含
    photographer),三个候选词集合都精确等于 {leon, paul}。白名单只要新增
    一个职业,就可能让"两个真人同名、本该两个都排除"变成"恰好一个排除失败、
    误判成那一个"——这正是"宁缺毋滥"最想防的那类错误,比多弃权几条严重得多。
    修法:photographer/architect 整体撤回(见 _OCCUPATION_WHITELIST 的注释)。"""
    from app.services.enrichment.material import resolve_creator_by_name

    def search(text, *, limit=5):
        if text != "Paul LEON":
            return []
        return [
            {"id": "Q115793023", "label": "Paul Leon", "match": {"text": "Paul Leon"}},
            {
                "id": "Q3371732",
                "label": "Paul Léon",
                "match": {"text": "Paul Léon"},
            },
            {
                "id": "Q128960542",
                "label": "Paul León",
                "match": {"text": "Paul León"},
            },
        ]

    def claims(qids):
        human = {"P31": [{"mainsnak": {"datavalue": {"value": {"id": "Q5"}}}}]}
        return {
            "Q115793023": {"claims": {**human, "P106": []}},
            "Q3371732": {
                "claims": {
                    **human,
                    "P106": [
                        {"mainsnak": {"datavalue": {"value": {"id": "Q121594"}}}}
                    ],  # professor
                }
            },
            "Q128960542": {
                "claims": {
                    **human,
                    "P106": [
                        {"mainsnak": {"datavalue": {"value": {"id": "Q1930187"}}}},
                        {
                            "mainsnak": {"datavalue": {"value": {"id": "Q33231"}}}
                        },  # photographer
                    ],
                }
            },
        }

    assert (
        resolve_creator_by_name("LEON Paul", search_entities=search, get_claims=claims)
        is None
    )


def test_resolve_creator_by_name_treats_uncertain_attribution_marker_as_qualifier():
    """真实 Joconde 数据里"(?)"表示"不确定是不是这个人画的",和"(d'après)"
    一样是弃权信号,不是普通噪声。真实案例"HUGO Charles (?);VACQUERIE Auguste"
    (已入库的历史数据,旧清洗正则没剥掉"(?)"因为那不是纯日期形态)——如果
    "(?)"不触发弃权闸,Hugo 那一段会因为带着字面"(?)"查不到(0 候选,被忽略),
    只剩 Vacquerie 那一段"成功",于是把本来"不确定是雨果还是瓦克里"的两可
    标注,错误坐实成"肯定是瓦克里"。"""
    from app.services.enrichment.material import resolve_creator_by_name

    def search_should_not_be_called(text, *, limit=5):
        raise AssertionError(f"(?) 弃权应该在拆分前拦住,不该查询 {text!r}")

    assert (
        resolve_creator_by_name(
            "HUGO Charles (?);VACQUERIE Auguste",
            search_entities=search_should_not_be_called,
        )
        is None
    )


def test_resolve_creator_by_name_abstains_on_bare_surname():
    """真实验证过(curl,`limit=5`——和生产代码的 `_SEARCH_LIMIT` 一致):裸
    姓氏"ROUSSEAU"搜索结果里排第一屏的 5 条是家族姓条目、Henri Rousseau
    (别名"Rousseau Douanier",词集合不精确相等,被滤掉)、Théodore Rousseau
    (Q310025,别名恰好就是裸姓氏"Rousseau")、Jean-Jacques Rousseau(哲学家,
    职业过滤会排除)、given name 条目。**同样是画家、同样有裸姓氏别名的
    Jacques Rousseau(Q6120842)排在第 8 位,`limit=5` 根本看不到他**——于是
    "唯一候选"规则被排名顺序意外满足,把"本该因为撞名而弃权"错误坐实成
    "肯定是 Théodore"。这不是候选集凑巧只有一个人,是单词查询本身就弱到
    排名说了算;真正的修法是单个词的署名段直接不产出候选,不进解析
    (spec 原意正是这个)。"""
    from app.services.enrichment.material import resolve_creator_by_name

    def search(text, *, limit=5):
        # limit=5 下真实返回的候选集(2026-10-07 curl 核实):画家 Jacques
        # Rousseau(Q6120842)排第 8,不在这 5 条里——这正是回归的根源。
        return [
            {"id": "Q16036532", "label": "Rousseau", "match": {"text": "Rousseau"}},
            {
                "id": "Q156386",
                "label": "Henri Rousseau",
                "match": {"text": "Rousseau Douanier"},
            },
            {
                "id": "Q310025",
                "label": "Théodore Rousseau",
                "match": {"text": "Rousseau"},
            },
            {
                "id": "Q6527",
                "label": "Jean-Jacques Rousseau",
                "match": {"text": "Rousseau"},
            },
            {
                "id": "Q111072568",
                "label": "Rousseau",
                "match": {"text": "Rousseau"},
            },
        ]

    def claims(qids):
        human = {"P31": [{"mainsnak": {"datavalue": {"value": {"id": "Q5"}}}}]}
        not_human = {
            "P31": [{"mainsnak": {"datavalue": {"value": {"id": "Q101352"}}}}]
        }  # family name
        painter = {"P106": [{"mainsnak": {"datavalue": {"value": {"id": "Q1028181"}}}}]}
        return {
            "Q16036532": {"claims": not_human},
            "Q310025": {"claims": {**human, **painter}},
            "Q6527": {
                "claims": {
                    **human,
                    "P106": [
                        {"mainsnak": {"datavalue": {"value": {"id": "Q36180"}}}}
                    ],  # writer, not in whitelist
                }
            },
            "Q111072568": {"claims": not_human},
        }

    assert (
        resolve_creator_by_name("ROUSSEAU", search_entities=search, get_claims=claims)
        is None
    )


import json as _json
from pathlib import Path as _Path

_E = _json.loads(
    (_Path(__file__).parents[3] / "fixtures" / "wikidata" / "entities.json").read_text()
)


def _fake_get(calls=None):
    def get(ids, *, props, languages=None):
        if calls is not None:
            calls.append((tuple(ids), props, tuple(languages or ())))
        return {q: _E[q] for q in ids if q in _E}

    return get


def test_fetch_wikidata_labels_real_shape_zh_variants():
    """真实夹具 Q35548(塞尚):zh 取 zh-hans→简体;zh-hant 链(无 zh-hant/zh-tw 时)取 zh 转繁,港式垫底。"""
    from app.services.enrichment.material import fetch_wikidata_labels

    calls = []
    out = fetch_wikidata_labels(
        "Q35548", ["en", "zh", "zh-hant"], get_entities=_fake_get(calls)
    )
    assert out["en"] == "Paul Cézanne"
    assert out["zh"] == _labels_expected_zh()
    assert calls[0][1] == "labels" and "zh-hans" in calls[0][2]


def _labels_expected_zh():
    from app.services.enrichment.material import _collapse_variants

    raw = {k: v["value"] for k, v in _E["Q35548"]["labels"].items()}
    return _collapse_variants(raw, ["zh"])["zh"]


def test_label_rows_match_sparql_shape():
    from app.services.enrichment.material import _label_rows

    rows = _label_rows(_E["Q35548"])
    assert {"l": {"xml:lang": "en", "value": "Paul Cézanne"}} in rows


import copy as _copy


def _p170(aq, rank="normal", certs=(), refs=0, snaktype="value"):
    """按真实夹具形状造 P170 语句(形状由 test_p170_helper_matches_real_shape 钉住)。"""
    st = _copy.deepcopy(_E["Q64309678"]["claims"]["P170"][0])
    st["rank"] = rank
    st["mainsnak"]["snaktype"] = snaktype
    if snaktype == "value":
        st["mainsnak"]["datavalue"]["value"]["id"] = aq
        st["mainsnak"]["datavalue"]["value"]["numeric-id"] = int(aq[1:])
    else:
        st["mainsnak"].pop("datavalue", None)
    q0 = _copy.deepcopy(_E["Q64309678"]["claims"]["P170"][0]["qualifiers"]["P1480"][0])
    quals = []
    for kind, val in certs:
        q = _copy.deepcopy(q0)
        q["snaktype"] = kind
        if kind == "value":
            q["datavalue"]["value"]["id"] = val
        else:
            q.pop("datavalue", None)
        quals.append(q)
    st["qualifiers"] = {"P1480": quals} if quals else {}
    ref0 = _E["Q64309678"]["claims"]["P170"][0]["references"][0]
    st["references"] = [_copy.deepcopy(ref0) for _ in range(refs)]
    return st


# ⚠️ 不能叫 _work:本文件已有 _work(n)(代表作测试在用),同名会整模块覆盖。
# 作品编号必须是 ^Q\d+$,否则被 resolve_creator_qid 的非 Wikidata 守卫直接返回 None,测试就不再走归组逻辑。
_WORK_QID = "Q900000001"


def _p170_entity(*sts):
    return {_WORK_QID: {"id": _WORK_QID, "claims": {"P170": list(sts)}}}


def _resolve(ents):
    from app.services.enrichment.material import resolve_creator_qid

    return resolve_creator_qid(_WORK_QID, get_entities=lambda ids, **k: ents)


def test_p170_helper_matches_real_shape():
    real = _E["Q64309678"]["claims"]["P170"][0]
    made = _p170("Q35548", certs=[("value", "Q18122778")], refs=1)
    assert made["mainsnak"] == real["mainsnak"]
    assert (
        made["qualifiers"]["P1480"][0]["datavalue"]
        == real["qualifiers"]["P1480"][0]["datavalue"]
    )


def test_resolve_creator_real_q64309678_prefers_cezanne():
    from app.services.enrichment.material import resolve_creator_qid

    assert resolve_creator_qid("Q64309678", get_entities=_fake_get()) == "Q35548"


def test_resolve_creator_real_unknown_value_is_none():
    from app.services.enrichment.material import resolve_creator_qid

    assert resolve_creator_qid("Q104479426", get_entities=_fake_get()) is None


def test_creator_refs_summed_across_duplicate_statements_changes_winner():
    """spec §3.1:同作者同 rank 同 cert 两条语句(2、3 条引用)→ 一个 refs=5 候选,胜过 refs=4 的 B。
    若不相加,A 最多 3 < 4,胜者会变成 B。"""
    ents = _p170_entity(_p170("Q1", refs=2), _p170("Q1", refs=3), _p170("Q2", refs=4))
    assert _resolve(ents) == "Q1"


def test_creator_multi_p1480_on_one_statement_uses_best():
    ents = _p170_entity(
        _p170(
            "Q1", certs=[("value", "Q30230067"), ("value", "Q18122778")]
        ),  # possibly + presumably
        _p170("Q2", certs=[("value", "Q30230067")], refs=5),  # possibly
    )
    assert _resolve(ents) == "Q1"


def test_creator_p1480_unknown_value_ranks_between_presumably_and_possibly():
    ents = _p170_entity(
        _p170("Q1", certs=[("somevalue", None)]),
        _p170("Q2", certs=[("value", "Q30230067")]),
    )
    assert _resolve(ents) == "Q1"
    ents = _p170_entity(
        _p170("Q1", certs=[("somevalue", None)]),
        _p170("Q3", certs=[("value", "Q18122778")]),
    )
    assert _resolve(ents) == "Q3"


def test_creator_p1480_novalue_counts_as_no_qualifier():
    ents = _p170_entity(
        _p170("Q1", certs=[("novalue", None)]),
        _p170("Q2", certs=[("value", "Q18122778")], refs=9),
    )
    assert _resolve(ents) == "Q1"


def test_creator_deprecated_and_unknown_statements_excluded():
    ents = _p170_entity(
        _p170("Q1", rank="deprecated", refs=9),
        _p170(None, snaktype="somevalue"),
        _p170("Q2"),
    )
    assert _resolve(ents) == "Q2"


def test_resolve_creator_skips_non_wikidata_id():
    from app.services.enrichment.material import resolve_creator_qid

    def boom(*a, **k):
        raise AssertionError("不该对非 Wikidata 编号发请求")

    assert resolve_creator_qid("joconde-00000089446", get_entities=boom) is None


def test_artist_facts_and_material_empty_without_artist_qid():
    """spec §2.2/§4.1:artist_qid 为空 = 无作者或故意弃权,不再遍历 P170(哈希作者的来源)。"""
    from app.services.enrichment.material import (
        fetch_artist_facts,
        fetch_artist_material,
    )

    def boom(*a, **k):
        raise AssertionError("artist_qid 为空时不该发请求")

    assert fetch_artist_facts("Q104479426", get_entities=boom) == {}
    assert (
        fetch_artist_material("Q104479426", SourceRegistry([]), get_entities=boom) == {}
    )


def test_fetch_artist_facts_real_cezanne_skips_deprecated_death():
    from app.services.enrichment.material import fetch_artist_facts

    f = fetch_artist_facts("Q64309678", get_entities=_fake_get(), artist_qid="Q35548")
    assert f["artist_qid"] == "Q35548"
    assert f["artist_birth"] == "1839" and f["artist_death"] == "1906"
    assert f["artist_nationality"] == "France"
    expected = [
        _E[s["mainsnak"]["datavalue"]["value"]["id"]]["labels"]["en"]["value"]
        for s in _E["Q35548"]["claims"]["P800"]
        if s["rank"] != "deprecated"
        and _E.get(s["mainsnak"]["datavalue"]["value"]["id"], {})
        .get("labels", {})
        .get("en")
    ][:5]
    assert f["artist_notable_works"] == expected


def test_fetch_artist_facts_real_raphael_tied_preferred_and_deprecated_nationality():
    """拉斐尔:P569 两条 preferred(同为 1483),P27 normal 意大利城邦 + deprecated Q38 → 取第一条、排除 deprecated。"""
    from app.services.enrichment.material import fetch_artist_facts

    f = fetch_artist_facts("Qx", get_entities=_fake_get(), artist_qid="Q5597")
    assert f["artist_birth"] == "1483" and f["artist_death"] == "1520"
    assert f["artist_nationality"] == _E["Q12548"]["labels"]["en"]["value"]


def test_fetch_artist_facts_unknown_birth_not_stored_as_http():
    """spec §4.2:生年是「未知值」时不再存成 'http'。"""
    from app.services.enrichment.material import fetch_artist_facts

    art = _copy.deepcopy(_E["Q35548"])
    art["claims"]["P569"][0]["mainsnak"]["snaktype"] = "somevalue"
    art["claims"]["P569"][0]["mainsnak"].pop("datavalue")
    f = fetch_artist_facts(
        "Qx",
        get_entities=lambda ids, **k: {
            "Q35548": art,
            **{q: _E[q] for q in ids if q in _E and q != "Q35548"},
        },
        artist_qid="Q35548",
    )
    assert "artist_birth" not in f and f["artist_death"] == "1906"


def test_artist_fact_rows_fill_raw_qid_when_no_english_label():
    from app.services.enrichment.material import _artist_fact_rows

    art = {"claims": {"P800": [_copy.deepcopy(_E["Q35548"]["claims"]["P800"][0])]}}
    art["claims"]["P800"][0]["mainsnak"]["datavalue"]["value"]["id"] = "Q999999999"
    rows = _artist_fact_rows(art, lambda ids, **k: {})
    assert rows == [{"workLabel": {"value": "Q999999999"}}]


def test_fetch_artist_i18n_real_cezanne_same_works_every_language():
    from app.services.enrichment.material import fetch_artist_i18n_facts

    calls = []
    out = fetch_artist_i18n_facts(
        "Q35548", ["en", "zh", "zh-hant"], get_entities=_fake_get(calls)
    )
    assert out["nationality_i18n"]["en"] == "France"
    assert out["nationality_i18n"]["zh"] == "法国"
    en, zh = out["notable_works_i18n"]["en"], out["notable_works_i18n"]["zh"]
    assert len(en) == len(zh) == len(out["notable_works_labels"]) <= 5
    assert "Mont Sainte-Victoire" in en and "圣维克多山" in zh
    assert (
        calls[0][1] == "claims" and calls[1][1] == "labels" and "zh-hans" in calls[1][2]
    )


def test_artist_i18n_rows_carry_work_qid_for_grouping():
    from app.services.enrichment.material import _artist_i18n_rows

    rows = _artist_i18n_rows(_E["Q35548"], ["en"], _fake_get())
    work_rows = [r for r in rows if "work" in r]
    assert work_rows and all(
        r["work"]["value"].startswith("http://www.wikidata.org/entity/Q")
        for r in work_rows
    )


def test_stored_hash_artist_qid_is_not_queried():
    """终审 #1:prod 存量 61 件的 artist_qid 是 32 位哈希;拿它去查只会报 no-such-entity
    并刷 prep 警告。三个作者函数都要先判 is_wikidata_qid。"""
    from app.services.enrichment.material import (
        fetch_artist_facts,
        fetch_artist_i18n_facts,
        fetch_artist_material,
    )

    def boom(*a, **k):
        raise AssertionError("哈希作者 QID 不该发请求")

    h = "6b3fdc5b548e4fdde651a18ead38c7ec"
    assert fetch_artist_facts("Q1", get_entities=boom, artist_qid=h) == {}
    assert (
        fetch_artist_material("Q1", SourceRegistry([]), get_entities=boom, artist_qid=h)
        == {}
    )
    assert fetch_artist_i18n_facts(h, ["en"], get_entities=boom) == {
        "nationality_i18n": {},
        "notable_works_i18n": {},
        "notable_works_labels": [],
    }


# ── P518「只适用于某部分」(10-14 用户真机《三美神》)────────────────────────
# 卢浮 Q18663545:P170 = 未知值(佚名) + 科尔迪耶(限定 P518=修复,1609)。旧代码丢掉未知值、
# 不看 P518 → 修复者成了唯一作者,导览写出「1567 年生的人在 150 年创作了它」。
# 但 P518 不全是修复:人物/花卉合作、底稿/织造常是真合作者,不能一律跳过。
_RESTORATION = "Q217102"


def _with_parts(st, *parts):
    """给 P170 语句挂 P518 限定(形状照 P1480 限定改属性名,值为 QID 或 None=未知值)。"""
    q0 = _copy.deepcopy(_E["Q64309678"]["claims"]["P170"][0]["qualifiers"]["P1480"][0])
    quals = []
    for p in parts:
        q = _copy.deepcopy(q0)
        q["property"] = "P518"
        if p is None:
            q["snaktype"] = "somevalue"
            q.pop("datavalue", None)
        else:
            q["datavalue"]["value"]["id"] = p
            q["datavalue"]["value"]["numeric-id"] = int(p[1:])
        quals.append(q)
    st.setdefault("qualifiers", {})["P518"] = quals
    return st


def test_creator_restorer_with_anonymous_whole_is_none():
    """三美神:整件佚名 + 修复者 → 作者不详,不是修复者。"""
    ents = _p170_entity(
        _p170(None, snaktype="somevalue"),
        _with_parts(_p170("Q3876426"), _RESTORATION),
    )
    assert _resolve(ents) is None


def test_creator_restoration_only_is_none():
    ents = _p170_entity(_with_parts(_p170("Q3876426", refs=3), _RESTORATION))
    assert _resolve(ents) is None


def test_creator_known_whole_and_partial_keep_old_ranking():
    """整件 + 已知部分作者:不改旧择优(prod 10-14 全库对比:「整件优先」会选出铸造工、
    换掉「习作」作者,得不偿失)。这里部分作者引用多 → 仍是它。"""
    ents = _p170_entity(
        _p170("Q1237940"),
        _with_parts(_p170("Q148475", refs=9), "Q5448026"),  # figure painting
    )
    assert _resolve(ents) == "Q148475"


def test_creator_partial_only_with_unknown_main_part_is_none():
    """《沉睡的赫马佛洛狄忒斯》形状:本体(部分)作者未知 + 贝尼尼只做床垫 → 不详。"""
    ents = _p170_entity(
        _with_parts(_p170(None, snaktype="somevalue"), "Q193474"),
        _with_parts(_p170("Q160538", refs=5), "Q1365497"),
    )
    assert _resolve(ents) is None


def test_creator_partial_only_collaboration_still_picks_one():
    """人物 + 花卉合作(全是已知的部分作者)→ 照旧按尺子挑一位,不弃权。"""
    ents = _p170_entity(
        _with_parts(_p170("Q1384115"), "Q12303833"),  # floral painting
        _with_parts(_p170("Q1358136", refs=2), "Q5448026"),  # figure painting
    )
    assert _resolve(ents) == "Q1358136"


def test_fetch_creators_batch_handles_partial_like_single():
    """批量路径同一套 P518 规则(三美神 + 合作件)。"""
    from app.services.enrichment.backfill import _fetch_creators

    def row(item, aq, part=None, refs=0):
        r = dict(
            _creator_row(aq, refs=refs, var="creator"),
            item={"value": f"http://www.wikidata.org/entity/{item}"},
        )
        if part:
            r["part"] = {"value": f"http://www.wikidata.org/entity/{part}"}
        return r

    rows = [
        row("Q18663545", "Q3876426", _RESTORATION),
        dict(
            row("Q18663545", "Q1"),
            creator={"value": "http://www.wikidata.org/.well-known/genid/7ad693ef"},
        ),
        row("Q29644503", "Q1384115", "Q12303833"),
        row("Q29644503", "Q1358136", "Q5448026", refs=2),
    ]
    assert _fetch_creators(["Q18663545", "Q29644503"], run_query=lambda s: rows) == {
        "Q29644503": "Q1358136"
    }


# ── 作者只采信注册账号版本(10-19,《喜鹊》Q4429116:临时账号把莫奈改成毕加索 3 个月) ──
_MONET, _PICASSO = "Q296", "Q5593"
_VANDAL = {"revid": 30, "user": "~2026-24823-27", "temp": ""}
_EDITOR = {"revid": 20, "user": "Shonagon"}


def _resolve_hist(current, revs, old=None, at_calls=None):
    from app.services.enrichment.material import resolve_creator_qid

    def at(revid):
        (at_calls if at_calls is not None else []).append(revid)
        return old

    return resolve_creator_qid(
        _WORK_QID,
        get_entities=lambda ids, **k: _p170_entity(_p170(current)),
        get_revisions=lambda q: revs,
        get_entity_at=at,
    )


def test_creator_vandal_period_uses_last_registered_revision():
    calls = []
    old = _p170_entity(_p170(_MONET))[_WORK_QID]
    assert _resolve_hist(_PICASSO, [_VANDAL, _EDITOR], old, calls) == _MONET
    assert calls == [20]


def test_creator_latest_registered_edit_uses_current_without_extra_fetch():
    calls = []
    assert _resolve_hist(_MONET, [_EDITOR, _VANDAL], None, calls) == _MONET
    assert calls == []


def test_creator_no_registered_revision_in_window_abstains():
    assert _resolve_hist(_PICASSO, [_VANDAL, {**_VANDAL, "revid": 29}]) is None


def test_creator_revision_lookup_failure_falls_back_to_current():
    from app.services.enrichment.material import resolve_creator_qid
    from app.services.enrichment.wikidata_api import WikidataApiError

    def boom(q):
        raise WikidataApiError("HTTP 503")

    assert (
        resolve_creator_qid(
            _WORK_QID,
            get_entities=lambda ids, **k: _p170_entity(_p170(_MONET)),
            get_revisions=boom,
        )
        == _MONET
    )


def test_artist_name_en_never_takes_work_credit_for_wikidata_qid():
    """作者英文名只认该 QID 自己的标签。10-20 prod 45 位作者 name_en 存成了合作者
    (Q314814 Philippe de Champaigne 被写成 Jean-Charles Tardieu):标签没取到时
    退回作品行署名,而多作者件的署名可能是另一个人。"""
    from app.services.enrichment.material import artist_name_en

    assert artist_name_en("Q314814", {"en": "Philippe de Champaigne"}, "X") == (
        "Philippe de Champaigne"
    )
    # 没有 en → 用该 QID 自己的拉丁字母标签,不用作品署名
    assert artist_name_en("Q1", {"fr": "Jean Dupont", "zh": "让"}, "Collab") == (
        "Jean Dupont"
    )
    # 一个标签都没有(含抓取失败)→ 留空待重跑,绝不填作品署名
    assert artist_name_en("Q314814", {}, "Jean-Charles Tardieu") is None
    assert artist_name_en("Q314814", None, "Jean-Charles Tardieu") is None
    assert artist_name_en("Q1", {"zh": "让"}, "Collab") is None  # 非拉丁不进 en 列
    # 非 Wikidata 把手(joconde-…)没有标签可查,作品署名是唯一来源
    assert artist_name_en("joconde-123", {}, "Jean Dupont") == "Jean Dupont"
