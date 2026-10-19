"""翻译规范名的「写法」与「指代」要分开(2026-09-26《驾驶邮车》实证)。

画中人是作者的父亲 Alphonse de Toulouse-Lautrec-Monfa,作者是 Henri。翻译 prompt 只给
作者译名、不给原名 → 韩语 3 次里 2 次把驾车的人写成作者「앙리」;而忠实度闸 STEP 0
叫判定模型「先删掉规范名字符串再判」→ 被换进去的恰好是那个字符串,满分放行。
检查侧的例外条款试过、A/B 证明有害已撤(见 build_faithfulness_prompt 注释),
所以这类错**只在翻译侧防** —— 下面前两条测试就是那道唯一的防线。
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


def test_faithfulness_knows_the_injected_museum_name():
    """纪律 22:翻译侧注入了馆名,检查侧必须知道,否则规范馆名会被判成错译。"""
    _, user = build_faithfulness_prompt("x", "y", "zh", museum="小皇宫美术馆")
    assert "museum -> 「小皇宫美术馆」" in user


def test_translation_prompt_ties_canonical_title_to_this_work_only():
    """10-19《荷马的脚,〈荷马的神化〉习作》Q29855229:原文提到「更大的构图《荷马的神化》」,
    西/法/日把它换成了本件整标题、简中/韩换成「…习作」,忠实度闸 3/3 放行。"""
    system, _ = build_translation_prompt(
        'A study for "The Apotheosis of Homer".',
        "es",
        title="Los pies de Homero, estudio para La apoteosis de Homero",
    )
    assert "ONLY to this artwork" in system
    assert "DIFFERENT works" in system
