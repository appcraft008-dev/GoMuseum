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
