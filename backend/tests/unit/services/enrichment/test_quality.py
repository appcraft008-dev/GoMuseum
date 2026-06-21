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

        if "entail" in system.lower():
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


def test_check_section_fact_conflict_forces_review():
    body = "Olympia was painted in 1900."
    gate = QualityGate(
        _FakeComplete(verdicts=[True], conflicts=["body says 1900, facts say 1863"])
    )
    r = gate.check_section("material", "- Year: 1863", body)
    assert r.conflicts == ["body says 1900, facts say 1863"]
    assert r.status == "needs_review"
    assert r.score == 0.5


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

            if "entail" in system.lower():
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
