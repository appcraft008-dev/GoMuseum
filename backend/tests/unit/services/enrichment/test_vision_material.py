"""视觉描述进材料包:钉住三件**出了错也不会报错**的事。

1. 描述有没有真的进材料(没进 = 白花钱,而生成照样跑得通、闸照样绿);
2. 来源标记有没有被当成材料喂进去(「gpt-4o/high」当材料 = 污染);
3. 视觉调用有没有夹带标题/作者(夹带 = 模型顺着标题编,正是我们要修的病)。
"""

import pytest

from app.services.enrichment.content_enricher import build_material
from app.services.enrichment.vision import build_vision_messages


def _obj(**attrs):
    return {
        "title_en": "The Donkey",
        "artist_en": "Gustave Courbet",
        "year": "1862",
        "attributes": attrs,
    }


def test_visual_description_enters_the_material():
    m = build_material(_obj(visual_description_en="A donkey in profile, head lowered."))
    assert "VISIBLE IN THE ARTWORK" in m
    assert "A donkey in profile, head lowered." in m


def test_material_says_the_description_came_from_a_photograph():
    """不标来源,接地闸就无从区分「暗调背景」是观察还是脑补 ——
    而闸的默认归类(IMPRESSION → KEEP)恰好是放行。"""
    m = build_material(_obj(visual_description_en="Muted, earthy background."))
    assert "photograph" in m.lower()


def test_provenance_marker_is_not_fed_to_the_model_as_material():
    """来源标记只是留痕,不能进材料。

    这条是防**命名**踩坑:若把标记取名 `visual_description_via`,
    它会被 `startswith("visual_description_")` 收进材料块,
    模型就会看到一行「gpt-4o/high」当作品信息 —— 不报错、不崩、只是脏。

    ⚠️ 键名从脚本里取,不在这儿写死 —— 否则改了脚本、测试照样绿。
    """
    from scripts.describe_artwork_images import _KEY, _VIA_KEY

    m = build_material(
        _obj(**{_KEY: "A donkey.", _VIA_KEY: "gpt-4o/high"}),
    )
    assert "A donkey." in m, "描述本身必须进材料"
    assert "gpt-4o" not in m, f"来源标记 {_VIA_KEY} 被当成材料喂进去了"


def test_no_visual_description_means_no_block():
    """没有描述时不要留一个空块 —— 空标题会让模型以为"看过图但没什么可说"。"""
    m = build_material(_obj(medium_fr="Peinture à l'huile"))
    assert "VISIBLE IN THE ARTWORK" not in m


def test_existing_material_blocks_still_present():
    """加法不破坏原有块(维基正文/作者传记/结构化事实)。"""
    o = _obj(visual_description_en="A donkey.", extract_en="Wiki body.")
    o["attributes"]["artist_extract_en"] = "Courbet was…"
    m = build_material(o)
    assert "[FACTS]" in m
    assert "[WIKIPEDIA EXTRACTS]" in m and "Wiki body." in m
    assert "[ABOUT THE ARTIST]" in m and "Courbet was…" in m


def test_vision_prompt_never_sees_title_or_artist():
    """不给标题是**设计**,不是疏忽。

    给了标题,模型就能顺着标题编:实测无视觉材料时,
    "Danaé" 这个标题足以让它写出「金雨倾泻、宙斯化身」整段神话解读。
    不给标题 → 它只能描述真正看见的东西。
    """
    msgs = build_vision_messages("https://cdn.example/img_large.jpg")
    blob = repr(msgs)
    assert "Donkey" not in blob and "Courbet" not in blob and "1862" not in blob


def test_vision_prompt_sends_the_image_with_requested_detail():
    msgs = build_vision_messages("https://cdn.example/img_large.jpg", detail="high")
    part = msgs[-1]["content"][0]
    assert part["type"] == "image_url"
    assert part["image_url"]["url"].endswith("_large.jpg")
    assert part["image_url"]["detail"] == "high"


def test_vision_prompt_forbids_naming_and_interpreting():
    """两条硬要求:①不许指名道姓 ②不许解读意义。

    ①防的是"看见一个女人就说这是萨拉·伯恩哈特";
    ②防的是描述里混进主观判断,那样它就不再是可核对的材料。
    """
    sys_msg = build_vision_messages("u")[0]["content"]
    assert "Do NOT identify people" in sys_msg
    assert "Do NOT interpret" in sys_msg
    assert "Do NOT describe the frame" in sys_msg


def test_vision_prompt_asks_to_transcribe_text_on_the_work():
    """作品**上**的文字要逐字转写 —— 漏它会连带看错东西。

    实测(奥赛《Credo》):不要求转写时,主体举着的、写有 CREDO 的横幅
    被读成「一把大弯刀,双手横持」;加上这条后改为「可能是横幅或布」。
    """
    sys_msg = build_vision_messages("u")[0]["content"]
    assert "Transcribe VERBATIM" in sys_msg
    assert "inscription" in sys_msg


def test_hedging_rule_lives_inside_the_transcription_sentence():
    """「读不清就说读不清」必须长在转写那一句上,不能只留在 prompt 末尾当通则。

    2026-09-13 实测(Q104444757 梅尔松草图):末尾通则版把 4 条铭文里的 3 条
    编了出来,而且编得合情合理(全是「体育协会」这类词) —— 下游当硬事实用,
    最难发现。同图 A/B 各 2 次:旧 3 条/3 条 → 新 1 条/0 条。
    这是 #555「禁令要长在它约束的那一拍上」的第二例,位置断言钉的就是这一点。
    """
    sys_msg = build_vision_messages("u")[0]["content"]
    i_transcribe = sys_msg.index("Transcribe VERBATIM")
    i_hedge = sys_msg.index("not\nclearly legible".replace("\n", " "))
    i_next_beat = sys_msg.index("Do NOT identify people")
    assert i_transcribe < i_hedge < i_next_beat, "约束必须在转写这一拍之内"
    assert "INSTEAD OF" in sys_msg, "要明说『不许重建它大概写了什么』"


def test_vision_prompt_asks_for_middle_distance():
    """只写显眼元素会漏掉主体。

    实测(奥赛《Bateaux sur l'Oise》):第一版描述只有树和红屋顶房子,
    **一条船都没提** —— 而船是这幅画的主题,就停在中景。
    """
    sys_msg = build_vision_messages("u")[0]["content"]
    assert "middle distance" in sys_msg
    assert "boats" in sys_msg


def test_vision_prompt_prefers_hedging_over_guessing():
    """看不清要说看不清,而不是猜一个具体东西。

    猜出来的「弯刀」进了材料就是**有据可依的假事实** —— 比没有材料更糟,
    因为接地闸会认为它被材料支持。
    """
    sys_msg = build_vision_messages("u")[0]["content"]
    assert "say it is unclear rather than guessing" in sys_msg


def test_describe_image_refuses_to_return_empty(monkeypatch):
    """空描述必须抛,不能当成"这张图没什么可说的"静默写进库。"""
    from app.services.enrichment import vision

    class _Resp:
        choices = [type("C", (), {"message": type("M", (), {"content": "   "})()})()]
        usage = type("U", (), {"prompt_tokens": 1, "completion_tokens": 0})()

    class _Client:
        class chat:
            class completions:
                @staticmethod
                async def create(**kw):
                    return _Resp()

    monkeypatch.setattr(
        "app.services.content_generation_service._get_openai_client",
        lambda: _Client(),
    )
    monkeypatch.setattr("app.services.llm_usage.record_llm_usage", lambda *a: None)
    with pytest.raises(RuntimeError):
        vision.describe_image("https://cdn.example/x_large.jpg")
