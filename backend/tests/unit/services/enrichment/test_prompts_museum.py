"""馆介绍生成 + 封面得体性 prompt。"""


def test_build_museum_intro_prompt_grounded_no_logistics():
    from app.services.enrichment.prompts import build_museum_intro_prompt

    system, user = build_museum_intro_prompt("Musée d'Orsay", "MATERIAL TEXT")
    assert "Musée d'Orsay" in user and "MATERIAL TEXT" in user
    assert "opening hours" in system  # 明令禁止运营数据
    # 分段走固定三具名字段JSON对象(2026-07-20交接+staging两轮实测修正:自由文本插
    # \n\n不可靠;变长数组{"paragraphs":[...]}对gpt-4o-mini约束力也不够,3/3真实
    # 调用被合并成单元素——具名必填字段才是够强的结构化约束)
    assert "history" in system and "highlights" in system and "invitation" in system
    assert "STRICT JSON" in system


def test_build_cover_safety_prompt_json_contract():
    from app.services.enrichment.prompts import build_cover_safety_prompt

    system, user = build_cover_safety_prompt(
        "L'Origine du monde", "Courbet", "painting"
    )
    assert "appropriate" in system and "Courbet" in user
