"""馆介绍生成 + 封面得体性 prompt。"""


def test_build_museum_intro_prompt_grounded_no_logistics():
    from app.services.enrichment.prompts import build_museum_intro_prompt

    system, user = build_museum_intro_prompt("Musée d'Orsay", "MATERIAL TEXT")
    assert "Musée d'Orsay" in user and "MATERIAL TEXT" in user
    assert "opening hours" in system  # 明令禁止运营数据


def test_build_cover_safety_prompt_json_contract():
    from app.services.enrichment.prompts import build_cover_safety_prompt

    system, user = build_cover_safety_prompt(
        "L'Origine du monde", "Courbet", "painting"
    )
    assert "appropriate" in system and "Courbet" in user
