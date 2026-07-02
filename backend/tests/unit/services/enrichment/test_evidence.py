def test_fetch_rich_facts_maps_props_to_topics():
    from app.services.enrichment.evidence import fetch_rich_facts

    def fake_run_query(sparql):
        return [
            {"pid": {"value": "P88"}, "vLabel": {"value": "Khalil Bey"}},
            {"pid": {"value": "P180"}, "vLabel": {"value": "female nude"}},
            {"pid": {"value": "P135"}, "vLabel": {"value": "Realism"}},
        ]

    facts = fetch_rich_facts("Q1", run_query=fake_run_query)
    by = {f["source"]: f for f in facts}
    assert (
        by["wikidata:P88"]["value"] == "Khalil Bey"
        and by["wikidata:P88"]["topic"] == "background"
    )
    assert by["wikidata:P180"]["topic"] == "analysis"
    assert by["wikidata:P135"]["topic"] == "significance"


def test_fetch_rich_facts_empty_on_no_rows():
    from app.services.enrichment.evidence import fetch_rich_facts

    assert fetch_rich_facts("Q1", run_query=lambda s: []) == []


def test_build_evidence_pack_assembles_facts_and_narrative():
    from app.services.enrichment.evidence import build_evidence_pack

    obj = {
        "qid": "Q1",
        "title_en": "Origin",
        "artist_en": "Courbet",
        "year": "1866",
        "attributes": {
            "medium_fr": "huile sur toile",
            "subjects_fr": "nu",
            "extract_en": "<work article>",
            "artist_extract_en": "<artist bio>",
        },
    }
    pack = build_evidence_pack(obj, run_query=lambda s: [], complete=None)
    fact_sources = {f["source"] for f in pack["facts"]}
    assert any("medium" in s for s in fact_sources)  # medium_fr → 事实
    assert any(s.startswith("object:") for s in fact_sources)  # 艺术家/年代/标题
    nsrc = {n["source"] for n in pack["narrative"]}
    assert "wikipedia:work" in nsrc and "wikipedia:artist" in nsrc
    assert all(n["type"] == "mainstream" for n in pack["narrative"])
    assert pack["flagged"] == []  # complete=None → 不抽争议

    # 含 tier 分级:medium 是 wall_label,subjects 是 material
    by_claim = {f["claim"]: f for f in pack["facts"]}
    assert by_claim["材质"]["tier"] == "wall_label"
    assert by_claim["主题"]["tier"] == "material"


def test_build_evidence_pack_rich_facts_network_failure_degrades():
    from app.services.enrichment.evidence import build_evidence_pack

    def boom(sparql):
        raise RuntimeError("wdqs down")

    obj = {"qid": "Q1", "title_en": "X", "attributes": {"extract_en": "t"}}
    pack = build_evidence_pack(obj, run_query=boom, complete=None)
    # 富属性失败不拖垮:基础事实 + narrative 仍在
    assert any(s.startswith("object:") for s in {f["source"] for f in pack["facts"]})
    assert any(n["source"] == "wikipedia:work" for n in pack["narrative"])


def test_extract_flagged_classifies_contested():
    import json as _json

    from app.services.enrichment.evidence import build_evidence_pack

    def fake(system, user):
        return _json.dumps(
            {
                "flagged": [
                    {"text": "研究者认为模特是 X", "type": "contested"},
                    {"text": "可能创作于战前", "type": "inference"},
                ]
            }
        )

    obj = {
        "qid": "Q1",
        "attributes": {
            "extract_en": "Scholars believe the model was X. Possibly made before the war."
        },
    }
    pack = build_evidence_pack(obj, run_query=lambda s: [], complete=fake)
    types = {f["type"] for f in pack["flagged"]}
    assert "contested" in types and "inference" in types


def test_extract_flagged_robust_on_llm_error():
    from app.services.enrichment.evidence import build_evidence_pack

    def boom(system, user):
        raise RuntimeError("llm down")

    pack = build_evidence_pack(
        {"qid": "Q1", "attributes": {"extract_en": "x"}},
        run_query=lambda s: [],
        complete=boom,
    )
    assert pack["flagged"] == []  # LLM 失败优雅降级


def test_fetch_rich_facts_relational_props():
    from app.services.enrichment.evidence import fetch_rich_facts

    rows = [
        {"pid": {"value": "P4969"}, "vLabel": {"value": "Later Homage"}},
        {"pid": {"value": "P144"}, "vLabel": {"value": "Titian Venus"}},
        {"pid": {"value": "P361"}, "vLabel": {"value": "Salon Series"}},
    ]
    facts = fetch_rich_facts("Q1", run_query=lambda s: rows)
    by = {f["source"]: f for f in facts}
    assert (
        by["wikidata:P4969"]["topic"] == "significance"
        and by["wikidata:P4969"]["claim"] == "影响了"
    )
    assert (
        by["wikidata:P144"]["topic"] == "background"
        and by["wikidata:P144"]["claim"] == "基于"
    )
    assert by["wikidata:P361"]["claim"] == "所属系列"


def test_fetch_rich_facts_caps_per_prop_at_5():
    from app.services.enrichment.evidence import fetch_rich_facts

    rows = [
        {"pid": {"value": "P4969"}, "vLabel": {"value": "d%d" % i}} for i in range(8)
    ]
    facts = fetch_rich_facts("Q1", run_query=lambda s: rows)
    assert len([f for f in facts if f["source"] == "wikidata:P4969"]) == 5  # 限5


def test_fetch_rich_facts_skips_raw_qid_labels():
    from app.services.enrichment.evidence import fetch_rich_facts

    rows = [
        {"pid": {"value": "P4969"}, "vLabel": {"value": "Q137160517"}},  # 无标签→跳
        {"pid": {"value": "P4969"}, "vLabel": {"value": "Real Homage"}},  # 有标签→留
    ]
    facts = fetch_rich_facts("Q1", run_query=lambda s: rows)
    vals = [f["value"] for f in facts if f["source"] == "wikidata:P4969"]
    assert vals == ["Real Homage"]  # QID-only 被过滤
