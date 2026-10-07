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


def test_fetch_artist_material_via_injected_query():
    from app.services.enrichment.material import fetch_artist_material
    from app.services.enrichment.registry import SourceRegistry
    from app.services.enrichment.sources.base import ObjectContribution, Source

    def fake_run_query(sparql):
        return [{"al_en": {"value": "https://en.wikipedia.org/wiki/Gustave_Courbet"}}]

    class _Wiki(Source):
        name = "wikipedia"

        def fetch(self, cfg):
            return []

        def enrich(self, qid, ext, ctx):
            t = (ctx.get("wiki_titles") or {}).get("en")
            return (
                ObjectContribution(
                    source="wikipedia",
                    qid=qid,
                    fields={"extract_en": f"bio of {t}"},
                    raw={},
                )
                if t
                else None
            )

    reg = SourceRegistry([_Wiki()])
    out = fetch_artist_material("Q1", reg, run_query=fake_run_query, country_lang="fr")
    assert out["artist_extract_en"] == "bio of Gustave_Courbet"


def test_fetch_artist_material_empty_when_no_artist():
    from app.services.enrichment.material import fetch_artist_material
    from app.services.enrichment.registry import SourceRegistry

    out = fetch_artist_material(
        "Q1", SourceRegistry([]), run_query=lambda s: [], country_lang="fr"
    )
    assert out == {}


def test_fetch_artist_facts_parses_structured():
    from app.services.enrichment.material import fetch_artist_facts

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

    f = fetch_artist_facts("Q1", run_query=fake)
    assert f["artist_birth"] == "1832" and f["artist_death"] == "1883"
    assert f["artist_nationality"] == "France"
    assert f["artist_notable_works"] == ["Olympia", "The Fifer"]  # 去重保序


def test_fetch_artist_facts_empty_on_no_rows():
    from app.services.enrichment.material import fetch_artist_facts

    assert fetch_artist_facts("Q1", run_query=lambda s: []) == {}


def test_fetch_artist_facts_skips_raw_qid_works():
    from app.services.enrichment.material import fetch_artist_facts

    def fake(sparql):
        return [
            {"workLabel": {"value": "Homage to Cézanne"}},
            {"workLabel": {"value": "Q17490760"}},  # 无标签→跳
            {"natLabel": {"value": "France"}},
        ]

    f = fetch_artist_facts("Q1", run_query=fake)
    assert f["artist_notable_works"] == ["Homage to Cézanne"]  # QID 被过滤
    assert f["artist_nationality"] == "France"


def test_fetch_artist_facts_returns_artist_qid():
    from app.services.enrichment.material import fetch_artist_facts

    def fake(sparql):
        return [
            {
                "artist": {"value": "http://www.wikidata.org/entity/Q296"},
                "natLabel": {"value": "Netherlands"},
            }
        ]

    f = fetch_artist_facts("Q1", run_query=fake)
    assert f["artist_qid"] == "Q296"


def test_fetch_wikidata_labels():
    from app.services.enrichment.material import fetch_wikidata_labels

    def fake(sparql):
        return [
            {"l": {"value": "La Nuit étoilée", "xml:lang": "fr"}},
            {"l": {"value": "Starry Night", "xml:lang": "en"}},
        ]

    out = fetch_wikidata_labels("Q1", ["en", "fr", "de"], run_query=fake)
    assert out == {"fr": "La Nuit étoilée", "en": "Starry Night"}  # 只含 Wikidata 有的


def test_fetch_artist_i18n_facts_multilang_labels():
    # 作者国籍(P27)/代表作(P800)的多语权威标签(交接③:非英语界面显英文)
    from app.services.enrichment.material import fetch_artist_i18n_facts

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
    out = fetch_artist_i18n_facts("Q296", ["zh", "en", "de"], run_query=lambda s: rows)
    assert out["nationality_i18n"] == {"zh": "法国", "en": "France", "de": "Frankreich"}
    assert out["notable_works_i18n"]["zh"] == ["奥林匹亚"]
    assert out["notable_works_i18n"]["en"] == ["Olympia"]


def test_fetch_artist_i18n_facts_skips_raw_qids_and_empty():
    from app.services.enrichment.material import fetch_artist_i18n_facts

    rows = [
        {"natLabel": {"value": "Q142", "xml:lang": "zh"}},  # 无标签退回QID→跳过
        {
            "work": {"value": "http://www.wikidata.org/entity/Q622062"},
            "workLabel": {"value": "Olympia", "xml:lang": "en"},
        },
    ]
    out = fetch_artist_i18n_facts("Q296", ["zh", "en"], run_query=lambda s: rows)
    assert "zh" not in out["nationality_i18n"]
    assert out["notable_works_i18n"]["en"] == ["Olympia"]
    # 中文没有权威标签 → 回退英文,而不是整条缺席:各语言列的必须是同一批作品
    assert out["notable_works_i18n"]["zh"] == ["Olympia"]


def test_fetch_labels_prefers_zh_hans_over_traditional():
    # 繁简混杂尾巴:Wikidata zh 标签变体不定(愛德華·馬奈)→ zh-hans > zh-cn > zh
    from app.services.enrichment.material import fetch_wikidata_labels

    rows = [
        {"l": {"value": "愛德華·馬奈", "xml:lang": "zh"}},
        {"l": {"value": "爱德华·马奈", "xml:lang": "zh-hans"}},
        {"l": {"value": "Édouard Manet", "xml:lang": "fr"}},
    ]
    out = fetch_wikidata_labels("Q296", ["zh", "fr"], run_query=lambda s: rows)
    assert out["zh"] == "爱德华·马奈"  # hans 优先于繁体 zh
    assert out["fr"] == "Édouard Manet"


def test_fetch_labels_zh_falls_back_when_no_hans():
    from app.services.enrichment.material import fetch_wikidata_labels

    rows = [{"l": {"value": "馬奈", "xml:lang": "zh"}}]
    out = fetch_wikidata_labels("Q296", ["zh"], run_query=lambda s: rows)
    assert out["zh"] == "马奈"  # 没 hans 时取 zh 并 t2s 转简


def test_zh_label_converted_to_simplified_when_only_traditional():
    # 根因:马奈/高更等在 Wikidata 只有繁体 zh 标签(无 zh-hans)→ OpenCC t2s 确定性转换
    from app.services.enrichment.material import fetch_wikidata_labels

    rows = [{"l": {"value": "愛德華·馬奈", "xml:lang": "zh"}}]
    out = fetch_wikidata_labels("Q40599", ["zh"], run_query=lambda s: rows)
    assert out["zh"] == "爱德华·马奈"  # 繁→简


def test_zh_hans_label_untouched():
    from app.services.enrichment.material import fetch_wikidata_labels

    rows = [{"l": {"value": "克劳德·莫奈", "xml:lang": "zh-hans"}}]
    out = fetch_wikidata_labels("Q296", ["zh"], run_query=lambda s: rows)
    assert out["zh"] == "克劳德·莫奈"


def test_artist_i18n_facts_zh_converted():
    from app.services.enrichment.material import fetch_artist_i18n_facts

    rows = [
        {"natLabel": {"value": "法國", "xml:lang": "zh"}},
        {
            "work": {"value": "http://www.wikidata.org/entity/Q622062"},
            "workLabel": {"value": "奧林匹亞", "xml:lang": "zh"},
        },
    ]
    out = fetch_artist_i18n_facts("Q40599", ["zh"], run_query=lambda s: rows)
    assert out["nationality_i18n"]["zh"] == "法国"
    assert out["notable_works_i18n"]["zh"] == ["奥林匹亚"]


def test_zh_hant_prefers_traditional_authoritative_label():
    from app.services.enrichment.material import fetch_wikidata_labels

    rows = [
        {"l": {"value": "顯現", "xml:lang": "zh-hant"}},
        {"l": {"value": "显现", "xml:lang": "zh-hans"}},
    ]
    out = fetch_wikidata_labels("Q1", ["zh-hant"], run_query=lambda s: rows)
    assert out["zh-hant"] == "顯現"  # 权威繁体优先


def test_zh_hant_converts_simplified_to_traditional_when_only_hans():
    from app.services.enrichment.material import fetch_wikidata_labels

    rows = [{"l": {"value": "爱德华·马奈", "xml:lang": "zh-hans"}}]
    out = fetch_wikidata_labels("Q296", ["zh-hant"], run_query=lambda s: rows)
    assert out["zh-hant"] == "愛德華·馬奈"  # 简→繁 s2t


def test_zh_hant_prefers_mandarin_over_cantonese_hk_label():
    """zh-hk 是粤语拼读的另一套音译传统,不能压过 zh 转繁。

    实测 Q35548 Cézanne:Wikidata 无 zh-hant/zh-tw 标签,zh-hk 标签是「保羅·施傘」,
    旧回退序取到它,于是每一段繁体讲解都把塞尚叫成施傘(污染 27 段)。
    """
    from app.services.enrichment.material import fetch_wikidata_labels

    rows = [
        {"l": {"value": "保羅·施傘", "xml:lang": "zh-hk"}},
        {"l": {"value": "保罗·塞尚", "xml:lang": "zh"}},
    ]
    out = fetch_wikidata_labels("Q35548", ["zh-hant"], run_query=lambda s: rows)
    assert out["zh-hant"] == "保羅·塞尚"


def test_zh_hant_still_uses_hk_label_as_last_resort():
    """但 zh-hk 仍留在链尾:它是唯一的中文标签时,人工标签好过机翻兜底。"""
    from app.services.enrichment.material import fetch_wikidata_labels

    rows = [{"l": {"value": "梵高", "xml:lang": "zh-hk"}}]
    out = fetch_wikidata_labels("Q5582", ["zh-hant"], run_query=lambda s: rows)
    assert out["zh-hant"] == "梵高"


def test_zh_still_simplified_regression():
    from app.services.enrichment.material import fetch_wikidata_labels

    rows = [{"l": {"value": "愛德華·馬奈", "xml:lang": "zh"}}]
    out = fetch_wikidata_labels("Q296", ["zh"], run_query=lambda s: rows)
    assert out["zh"] == "爱德华·马奈"  # 繁→简,回归不破


def test_non_variant_language_not_converted():
    from app.services.enrichment.material import fetch_wikidata_labels

    rows = [{"l": {"value": "エドゥアール・マネ", "xml:lang": "ja"}}]
    out = fetch_wikidata_labels("Q296", ["ja"], run_query=lambda s: rows)
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
        fetch_wikidata_labels,
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

    single = fetch_wikidata_labels(
        "Q12418",
        ["en", "zh"],
        run_query=lambda s: [
            {"l": {"xml:lang": "en", "value": "Mona Lisa"}},
            {"l": {"xml:lang": "zh-hans", "value": "蒙娜丽莎"}},
        ],
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
    from app.services.enrichment.material import fetch_artist_i18n_facts

    langs = ["en", "zh", "ja"]
    out = fetch_artist_i18n_facts("Q1", langs, run_query=lambda s: _rows_uneven())
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
    from app.services.enrichment.material import fetch_artist_i18n_facts

    rows = _rows_uneven()
    a = fetch_artist_i18n_facts("Q1", ["en", "zh", "ja"], run_query=lambda s: rows)
    b = fetch_artist_i18n_facts(
        "Q1", ["ja", "en", "zh"], run_query=lambda s: list(reversed(rows))
    )
    assert a["notable_works_i18n"]["en"] == b["notable_works_i18n"]["en"]


def test_notable_works_caps_at_five_by_label_coverage():
    """超过 5 件时,按"被标注得最全"取前 5(近似最知名),同分按 qid 稳定排。"""
    from app.services.enrichment.material import fetch_artist_i18n_facts

    rows = []
    for n in range(201, 208):  # 7 件,en 都有
        rows.append(
            {"work": _work(n), "workLabel": {"value": f"Q{n}-en", "xml:lang": "en"}}
        )
    for n in (207, 206):  # 这两件另有中文标签 → 覆盖度更高,应排最前
        rows.append(
            {"work": _work(n), "workLabel": {"value": f"Q{n}-zh", "xml:lang": "zh"}}
        )
    out = fetch_artist_i18n_facts("Q1", ["en", "zh"], run_query=lambda s: rows)
    got = out["notable_works_i18n"]["en"]
    assert len(got) == 5
    assert got[:2] == ["Q206-en", "Q207-en"], got  # 覆盖度 2 的排前,同分按 qid


def test_notable_works_zh_hant_converts_from_zh_not_english():
    """繁体没有权威标签时应走简体转繁(字形变体,确定性),而不是掉到英文。"""
    from app.services.enrichment.material import fetch_artist_i18n_facts

    rows = [
        {"work": _work(301), "workLabel": {"value": "Olympia", "xml:lang": "en"}},
        {"work": _work(301), "workLabel": {"value": "奥林匹亚", "xml:lang": "zh"}},
    ]
    out = fetch_artist_i18n_facts("Q1", ["en", "zh-hant"], run_query=lambda s: rows)
    assert out["notable_works_i18n"]["zh-hant"] == ["奧林匹亞"]


def test_artist_i18n_query_selects_every_binding_the_parser_reads():
    """解析侧按 row["work"] 给作品分组,查询就必须 SELECT ?work。

    ⚠️ 上面那些桩数据单测**永远抓不到这一条** —— 桩里的 work 字段是我自己造的,
    它当然在。真实查询漏 SELECT 时解析侧读到空,works 全空、返回 {} ——
    库里数据不会被抹(合并时空字典不覆盖),但**整个修复静默失效**:
    单测全绿、上线后一点变化都没有。
    """
    from app.services.enrichment.material import _ARTIST_I18N_FACTS_QUERY

    selected = _ARTIST_I18N_FACTS_QUERY.split("WHERE")[0].split()
    for var in ("?natLabel", "?work", "?workLabel"):
        assert var in selected, f"{var} 没进 SELECT,解析侧只会读到空"


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
    from app.services.enrichment.material import resolve_creator_qid

    assert resolve_creator_qid("Q64309678", run_query=lambda s: _Q64309678) == "Q35548"
    # 行序不该影响结果 —— SPARQL 不保证顺序,这正是旧代码的病根
    assert (
        resolve_creator_qid("Q64309678", run_query=lambda s: _Q64309678[::-1])
        == "Q35548"
    )


def test_resolve_creator_rank_beats_qualifier():
    from app.services.enrichment.material import resolve_creator_qid

    rows = [
        _creator_row("Q1", cert="Q30230067", rank="PreferredRank"),
        _creator_row("Q2", refs=9),  # 无限定 + 多引用,但只是 normal rank
    ]
    assert resolve_creator_qid("Qx", run_query=lambda s: rows) == "Q1"


def test_resolve_creator_skips_blank_node_and_deprecated():
    from app.services.enrichment.material import resolve_creator_qid

    rows = [
        {
            "artist": {"value": "http://www.wikidata.org/.well-known/genid/abc123"},
            "rank": {"value": "http://wikiba.se/ontology#NormalRank"},
        },
        _creator_row("Q7", rank="DeprecatedRank"),
    ]
    assert resolve_creator_qid("Qx", run_query=lambda s: rows) is None


def test_fetch_artist_facts_with_artist_qid_does_not_traverse_p170():
    """给定作者时必须直接问该实体 —— 否则多作者会逐行串味(qid 来自 A、生年来自 B)。"""
    from app.services.enrichment.material import fetch_artist_facts

    seen = {}

    def fake(sparql):
        seen["sparql"] = sparql
        return [{"birth": {"value": "1839-01-19T00:00:00Z"}}]

    f = fetch_artist_facts("Q64309678", run_query=fake, artist_qid="Q35548")
    assert "wdt:P170" not in seen["sparql"] and "wd:Q35548" in seen["sparql"]
    assert f["artist_qid"] == "Q35548" and f["artist_birth"] == "1839"


def test_fetch_artist_material_with_artist_qid_does_not_traverse_p170():
    from app.services.enrichment.material import fetch_artist_material
    from app.services.enrichment.registry import SourceRegistry

    seen = {}

    def fake(sparql):
        seen["sparql"] = sparql
        return []

    fetch_artist_material(
        "Q64309678", SourceRegistry([]), run_query=fake, artist_qid="Q35548"
    )
    assert "wdt:P170" not in seen["sparql"] and "wd:Q35548" in seen["sparql"]


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

    # 单词姓氏:3个词,2种切法(k=1,k=2)
    assert _reorder_candidates("SOUTINE Chaïm") == ["Chaïm SOUTINE"]
    # 多词姓氏(真实橘园数据:4个词,3种切法k=1,2,3)——必须覆盖所有切法,
    # 不能只试"第一个词挪到末尾"这一种:k=1 对这个真实案例是错的切法
    # (2026-10-07 实测:"CONSTANT Jean Joseph Benjamin"真正能命中
    # Wikidata 的切法不是只移一个词,而是把 k=1 时整串重排的结果
    # "Jean Joseph Benjamin CONSTANT"——这正是下面要断言在候选列表里的那条)。
    result = _reorder_candidates("CONSTANT Jean Joseph Benjamin")
    assert "Jean Joseph Benjamin CONSTANT" in result
    assert len(result) == 3  # 4个词,n-1=3种切法
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


def test_resolve_creator_by_name_whitelist_covers_photographer_and_architect():
    """2026-10-07 在 staging 对奥赛全馆跑 dry-run 时发现的真实缺口:职业
    白名单原本不收 photographer/architect,奥赛收藏里雨果流亡泽西岛期间的
    摄影圈子(Auguste Vacquerie Q940439,真实 P106 含 photographer Q33231)
    和建筑师(Georges-Ernest Coquart Q3102074,P106=architect Q42973)系统
    性弃权(前者单独命中 16 次)。按 spec §3.2 步骤3"遇到白名单漏掉的职业
    按实际案例补"的既定政策,这里补上这两个真实验证过的职业。"""
    from app.services.enrichment.material import resolve_creator_by_name

    def make_search(qid, match_text, occupation_qid):
        def _search(text, *, limit=5):
            return [{"id": qid, "label": match_text, "match": {"text": match_text}}]

        return _search

    def make_claims(qid, occupation_qid):
        def _claims(qids):
            return {
                qid: {
                    "claims": {
                        "P31": [{"mainsnak": {"datavalue": {"value": {"id": "Q5"}}}}],
                        "P106": [
                            {
                                "mainsnak": {
                                    "datavalue": {"value": {"id": occupation_qid}}
                                }
                            }
                        ],
                    }
                }
            }

        return _claims

    got = resolve_creator_by_name(
        "VACQUERIE Auguste",
        search_entities=make_search("Q940439", "Auguste Vacquerie", "Q33231"),
        get_claims=make_claims("Q940439", "Q33231"),
    )
    assert got == "Q940439"

    got = resolve_creator_by_name(
        "COQUART Ernest Georges",
        search_entities=make_search("Q3102074", "Georges-Ernest Coquart", "Q42973"),
        get_claims=make_claims("Q3102074", "Q42973"),
    )
    assert got == "Q3102074"
