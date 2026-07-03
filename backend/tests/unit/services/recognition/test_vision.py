"""识别器:一次 GPT 视觉调用给候选名(查询非答案,R1)+顺带转写可见文字;label 模式纯转写。
complete 注入离线测。spec 2026-07-03-recognition-design。"""

import json

from app.services.recognition.vision import identify


def test_identify_parses_candidates_and_label():
    def fake(system, user_content):
        return json.dumps(
            {
                "candidates": [{"title": "Olympia", "artist": "Édouard Manet"}],
                "label_text": "Olympia\nÉdouard Manet\n1863",
                "self_confidence": "high",
            }
        )

    out = identify("b64data", complete=fake)
    assert out["candidates"][0]["title"] == "Olympia"
    assert out["candidates"][0]["artist"] == "Édouard Manet"
    assert "1863" in out["label_text"]
    assert out["self_confidence"] == "high"


def test_identify_bad_json_returns_empty_not_raise():
    out = identify("b64data", complete=lambda s, u: "not json at all")
    assert out == {"candidates": [], "label_text": None, "self_confidence": "low"}


def test_identify_exception_returns_empty_not_raise():
    def boom(s, u):
        raise RuntimeError("llm down")

    out = identify("b64data", complete=boom)
    assert out["candidates"] == []


def test_label_mode_prompt_is_transcribe_only():
    seen = {}

    def fake(system, user_content):
        seen["system"] = system
        return json.dumps({"candidates": [], "label_text": "Le Chat blanc"})

    out = identify("b64data", mode="label", complete=fake)
    assert "transcribe" in seen["system"].lower()
    assert "identify" not in seen["system"].lower()
    assert out["label_text"] == "Le Chat blanc"


def test_artwork_mode_prompt_identifies_and_transcribes():
    seen = {}

    def fake(system, user_content):
        seen["system"] = system
        return json.dumps({"candidates": []})

    identify("b64data", complete=fake)
    s = seen["system"].lower()
    assert "identify" in s and "transcribe" in s
    assert "query" in s or "candidate" in s  # 强调候选是查询用途
