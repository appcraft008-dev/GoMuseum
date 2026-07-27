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

    rows = [
        {
            "natLabel": {"value": "法国", "xml:lang": "zh"},
            "workLabel": {"value": "奥林匹亚", "xml:lang": "zh"},
        },
        {
            "natLabel": {"value": "France", "xml:lang": "en"},
            "workLabel": {"value": "Olympia", "xml:lang": "en"},
        },
        {
            "natLabel": {"value": "Frankreich", "xml:lang": "de"},
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
        {"workLabel": {"value": "Olympia", "xml:lang": "en"}},
    ]
    out = fetch_artist_i18n_facts("Q296", ["zh", "en"], run_query=lambda s: rows)
    assert "zh" not in out["nationality_i18n"]
    assert out["notable_works_i18n"]["en"] == ["Olympia"]


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
        {"workLabel": {"value": "奧林匹亞", "xml:lang": "zh"}},
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
