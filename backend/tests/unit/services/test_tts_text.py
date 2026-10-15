"""切句器:Google 流式会静默吞超长句句尾(spec §2.3),切点必须改句号。"""

import re

from app.services.tts_text import split_sentences

LONG_ZH = (
    "这幅画不仅捕捉了一顿饭，更是思想的聚会——保罗·维尔伦、阿尔图尔·兰波及他们的同时代人"
    "——每个人都沉浸在思考或交谈中，他们的黑色服装与眼前生动的静物形成鲜明对比。"
)


def _letters(s):
    return re.sub(r"[\s。！？.!?，；：、,;:]", "", s)


def test_cjk_sentence_ends():
    assert split_sentences("第一句。第二句！第三句？", "zh") == [
        "第一句。",
        "第二句！",
        "第三句？",
    ]


def test_latin_decimals_and_short_fragments():
    # 1.5 不切;"Is it?" "Yes!" 都 < 12 字符,并成一句
    assert split_sentences("It is 1.5 m wide. Is it? Yes!", "en") == [
        "It is 1.5 m wide.",
        "Is it? Yes!",
    ]


def test_latin_split_on_period_space():
    out = split_sentences("This painting is large. It hangs in the Louvre today.", "en")
    assert out == ["This painting is large.", "It hangs in the Louvre today."]


def test_ellipsis_not_split():
    out = split_sentences("She waited... then the light changed over the river.", "en")
    assert out == ["She waited... then the light changed over the river."]


def test_abbreviation_not_split():
    out = split_sentences("We visit St. Peter's Basilica in the morning light.", "en")
    assert out == ["We visit St. Peter's Basilica in the morning light."]
    out = split_sentences(
        "It belonged to Walter Mme. Vve Jean before the museum bought it.", "es"
    )
    assert len(out) == 1


def test_qa_newlines_split():
    out = split_sentences(
        "What is this painting about?\n\nIt is a painting by Manet.", "en"
    )
    assert out == ["What is this painting about?", "It is a painting by Manet."]


def test_long_zh_sentence_split_with_periods():
    out = split_sentences(LONG_ZH, "zh")
    assert len(out) >= 2
    assert all(len(s) <= 60 for s in out)
    assert all(s.endswith("。") for s in out)
    assert "".join(_letters(s) for s in out) == _letters(LONG_ZH)


def test_ja_threshold_95():
    s = "あ" * 50 + "、" + "い" * 45 + "。"  # 97 字
    out = split_sentences(s, "ja")
    assert len(out) == 2 and all(len(x) <= 95 for x in out) and out[0].endswith("。")


def test_latin_threshold_270():
    s = ("word " * 40).strip() + ", " + ("more " * 20).strip() + "."  # > 270
    out = split_sentences(s, "fr")
    assert all(len(x) <= 270 for x in out) and out[0].endswith(".")


def test_hard_cut_without_commas():
    s = "字" * 130 + "。"
    out = split_sentences(s, "zh")
    assert all(len(x) <= 60 for x in out) and all(x.endswith("。") for x in out)
    assert "".join(_letters(x) for x in out) == "字" * 130


def test_empty_and_blank():
    assert split_sentences("", "en") == []
    assert split_sentences("  \n\n ", "zh") == []
