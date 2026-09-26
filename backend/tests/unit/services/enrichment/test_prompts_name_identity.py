"""翻译规范名的「写法」与「指代」要分开(2026-09-26《驾驶邮车》实证)。

画中人是作者的父亲 Alphonse de Toulouse-Lautrec-Monfa,作者是 Henri。翻译 prompt 只给
作者译名、不给原名 → 韩语 3 次里 2 次把驾车的人写成作者「앙리」;而忠实度闸 STEP 0
叫判定模型「先删掉规范名字符串再判」→ 被换进去的恰好是那个字符串,满分放行。
"""

from app.services.enrichment.prompts import (
    build_faithfulness_prompt,
    build_translation_prompt,
)


def test_translation_prompt_ties_canonical_name_to_one_person():
    system, _ = build_translation_prompt(
        "Alphonse drives the coach.",
        "ko",
        artist="앙리 드 툴루즈로트레크",
        artist_en="Henri de Toulouse-Lautrec",
    )
    assert "ONLY to Henri de Toulouse-Lautrec" in system
    assert "share the artist's surname" in system


def test_translation_prompt_unchanged_without_english_name():
    """老调用方(不传 artist_en)行为不变 —— 不能凭空写出一个 None 的作者名。"""
    system, _ = build_translation_prompt("x", "ko", artist="앙리")
    assert "share the artist's surname" not in system and "None" not in system


def test_faithfulness_exemption_covers_spelling_not_identity():
    _, user = build_faithfulness_prompt(
        "Alphonse drives.",
        "앙리가 운전한다.",
        "ko",
        artist="앙리 드 툴루즈로트레크",
        artist_en="Henri de Toulouse-Lautrec",
    )
    i0, i1 = user.index("STEP 0"), user.index("STEP 1")
    rule = user.index("wrong-person error")
    assert i0 < rule < i1, "指代例外必须写在 STEP 0 豁免之后、STEP 1 之前"
    assert "Henri de Toulouse-Lautrec" in user


def test_faithfulness_knows_the_injected_museum_name():
    """纪律 22:翻译侧注入了馆名,检查侧必须知道,否则规范馆名会被判成错译。"""
    _, user = build_faithfulness_prompt("x", "y", "zh", museum="小皇宫美术馆")
    assert "museum -> 「小皇宫美术馆」" in user
