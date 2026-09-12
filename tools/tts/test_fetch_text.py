"""取正文的挑段逻辑 —— 这里出错是**静默**的:整类段落被判"无文本,跳过",
状态里写 no_text,看起来像内容缺失而不是 bug。实测踩过一次(字段名 code/section_code)。
"""

import pathlib

from fetch_text import pick_section

RESP = {
    "default_guide": {"body": "主讲解正文"},
    "artist": {"bio": "作者小传"},
    "suggested_questions": [
        {"sort": 0, "question": "问零?", "answer": "答零"},
        {"sort": 1, "question": "问一?", "answer": "答一"},
    ],
    "tabs": [
        {"section_code": "background", "body": "背景正文"},
        {"section_code": "analysis", "body": "分析正文"},
    ],
}


def test_深度段按_section_code_取():
    """🔴 字段名是 section_code 不是 code。写成 code 时恒为 None,
    深度段会**全部**被跳过 —— 而第一批只做 guide,根本走不到这行,一直没暴露。"""
    assert pick_section(RESP, "background") == "背景正文"
    assert pick_section(RESP, "analysis") == "分析正文"


def test_guide_与_artist_bio_各走各的字段():
    assert pick_section(RESP, "guide") == "主讲解正文"
    assert pick_section(RESP, "artist_bio") == "作者小传"


def test_qa_是问答连念():
    """分开念会内容对不上:质检拿"问+答"全文比对,只念答案必然判失败。"""
    assert pick_section(RESP, "qa_1") == "问一?\n\n答一"


def test_取不到返回_None_而不是空串或抛错():
    """取不到要能被 `if not text` 认出来,跑批才会记 no_text 跳过而不是崩掉整轮。"""
    assert pick_section(RESP, "qa_9") is None
    assert pick_section(RESP, "不存在的段") is None
    assert pick_section({}, "guide") is None


def test_run_batch_复用这一份实现而不是自己抄一遍():
    """⚠️ 守的是**唯一性**。这段逻辑曾在实验室脚本里被抄过两遍,
    抄出来的副本和真跑批的那份可以独立走样,而走样是静默的。"""
    src = (pathlib.Path(__file__).parent / "run_batch.py").read_text(encoding="utf-8")
    assert "from fetch_text import fetch_text" in src, "run_batch.py 没引用共用实现"
    assert "def fetch_text(" not in src, "run_batch.py 又自己定义了一份 fetch_text"
