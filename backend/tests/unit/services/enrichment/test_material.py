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
