from app.services.enrichment.prompts import build_generation_prompt


def test_prompt_lists_requested_sections_and_grounding_rules():
    system, user = build_generation_prompt(
        material="[FACTS]\n- Title: X",
        sections=["overview", "artist"],
        category="painting",
    )
    assert "only" in system.lower()
    assert "overview" in user and "artist" in user
    assert "painting" in user
    assert "[FACTS]" in user


def test_entailment_prompt_demands_per_sentence_json_verdicts():
    from app.services.enrichment.prompts import build_entailment_prompt

    system, user = build_entailment_prompt("[FACTS]\n- Title: Olympia", ["S1.", "S2."])
    blob = (system + user).lower()
    assert "only" in blob and "material" in blob
    assert "json" in blob
    assert "verdicts" in blob
    assert "S1." in user and "S2." in user


def test_fact_consistency_prompt_lists_conflicts_json():
    from app.services.enrichment.prompts import build_fact_consistency_prompt

    system, user = build_fact_consistency_prompt(
        "- Year: 1863", "Painted in 1900 by Manet."
    )
    blob = (system + user).lower()
    assert "contradict" in blob or "conflict" in blob
    assert "json" in blob
    assert "conflicts" in blob
    assert "1863" in user and "1900" in user
