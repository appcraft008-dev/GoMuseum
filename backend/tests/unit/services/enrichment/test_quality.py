from app.services.enrichment.quality import _split_sentences


def test_split_sentences_basic():
    text = "Olympia is a painting. It caused a scandal. Monet led a subscription."
    assert _split_sentences(text) == [
        "Olympia is a painting.",
        "It caused a scandal.",
        "Monet led a subscription.",
    ]


def test_split_sentences_strips_empty_and_whitespace():
    assert _split_sentences("  One sentence only.  ") == ["One sentence only."]
    assert _split_sentences("") == []
    assert _split_sentences(None) == []


from app.services.enrichment.quality import QualityGate, SectionQuality


class _FakeComplete:
    """按 system 内容路由：蕴含 prompt 返 verdicts，事实 prompt 返 conflicts。"""

    def __init__(self, verdicts, conflicts):
        self._verdicts = verdicts
        self._conflicts = conflicts

    def __call__(self, system, user):
        import json as _json

        # system prompt 现用 "grounding judge"（三类判定语义），不再含 "entail"
        if "grounding judge" in system.lower():
            return _json.dumps({"verdicts": self._verdicts})
        return _json.dumps({"conflicts": self._conflicts})


def test_check_section_drops_unsupported_sentence():
    body = "Olympia is an 1863 painting. Manet pioneered Impressionism."
    gate = QualityGate(_FakeComplete(verdicts=[True, False], conflicts=[]))
    r = gate.check_section("[FACTS]\n- Year: 1863", "- Year: 1863", body)
    assert r.body == "Olympia is an 1863 painting."
    assert r.grounding_ratio == 0.5
    assert r.conflicts == []
    assert r.status == "needs_review"


def test_check_section_all_supported_no_conflict_publishes():
    body = "Olympia is an 1863 painting. It now hangs in the Musee d'Orsay."
    gate = QualityGate(_FakeComplete(verdicts=[True, True], conflicts=[]))
    r = gate.check_section("material", "facts", body)
    assert r.grounding_ratio == 1.0
    assert r.status == "published"
    assert r.score == 1.0


def test_check_section_grounded_publishes_regardless_of_facts():
    # 接地是唯一硬闸：每句被材料支持(grounding=1.0)即 published；
    # 不再做阻塞性 fact-consistency（对 Joconde 事件年高频误报、误杀已接地内容）。
    body = "The painting was first exhibited in 1869."
    gate = QualityGate(
        _FakeComplete(verdicts=[True], conflicts=["bogus year conflict"])
    )
    r = gate.check_section("material", "- Creation year: 1868", body)
    assert r.status == "published"
    assert r.grounding_ratio == 1.0
    assert r.score == 1.0
    assert r.conflicts == []  # 不再做事实对账，conflicts 恒空


def test_check_section_all_dropped_returns_none_body():
    body = "Totally made up sentence."
    gate = QualityGate(_FakeComplete(verdicts=[False], conflicts=[]))
    r = gate.check_section("material", "facts", body)
    assert r.body is None
    assert r.grounding_ratio == 0.0
    assert r.status == "needs_review"


def test_gate_runs_each_section_and_skips_absent():
    # overview 全支持→published；artist 全删→needs_review；analysis 输入为 None→跳过不进结果
    class _Router:
        def __call__(self, system, user):
            import json as _json

            if "grounding judge" in system.lower():
                return (
                    _json.dumps({"verdicts": [True]})
                    if "Overview sentence." in user
                    else _json.dumps({"verdicts": [False]})
                )
            return _json.dumps({"conflicts": []})

    gate = QualityGate(_Router())
    sections = {
        "overview": "Overview sentence.",
        "artist": "Fabricated artist sentence.",
        "analysis": None,
    }
    out = gate.gate("material", "facts", sections)
    assert set(out.keys()) == {"overview", "artist"}
    assert out["overview"].status == "published"
    assert out["artist"].status == "needs_review"
    assert out["artist"].body is None


def test_quality_gate_constructible_with_default_complete():
    from app.services.enrichment.content_enricher import default_complete
    from app.services.enrichment.quality import QualityGate

    gate = QualityGate(default_complete)  # 不调用，只验证可构造、签名兼容
    assert callable(gate._complete)


def test_gate_keeps_guidance_and_drops_unsupported_claim():
    import json as _json

    def fake(system, user):
        return _json.dumps({"verdicts": [True, False, True]})

    from app.services.enrichment.quality import QualityGate

    g = QualityGate(fake)
    body = (
        "Notice the red in the corner. It was painted in 1505. The mood feels uneasy."
    )
    r = g.check_section("MAT", "FACTS", body)
    assert "Notice the red" in r.body and "mood feels uneasy" in r.body
    assert "1505" not in r.body  # 无据事实被删
    assert r.status == "published"  # 存活 2/3 ≥ 阈值


def test_gate_needs_review_when_mostly_unsupported():
    import json as _json

    def fake(system, user):
        return _json.dumps({"verdicts": [False, False, True]})

    from app.services.enrichment.quality import QualityGate

    r = QualityGate(fake).check_section("MAT", "F", "A. B. C.")
    assert r.status == "needs_review"  # 存活 1/3 < 阈值


def test_en_axis_rejects_non_english():
    # en 轴心须英文:接地过但 body 是法语(镜像法语源)→needs_review
    from app.services.enrichment.quality import QualityGate

    def fake(system, user):
        return '{"verdicts": [true, true, true, true, true]}'

    gate = QualityGate(fake)
    q = gate.check_section(
        "material",
        "facts",
        "Ceci est une phrase française qui a fui dans l'axe anglais du contenu artistique.",
    )
    assert q.status == "needs_review"
