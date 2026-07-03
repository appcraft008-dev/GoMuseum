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


def test_default_complete_awaits_async_client(monkeypatch):
    # staging 教训:_get_openai_client 返回 AsyncOpenAI,漏 await → 协程当响应用 → 静默空结果
    import app.services.recognition.vision as vision

    class _Msg:
        content = '{"candidates": [], "label_text": "ok"}'

    class _Choice:
        message = _Msg()

    class _Resp:
        choices = [_Choice()]

    class _Completions:
        async def create(self, **kw):
            return _Resp()

    class _Chat:
        completions = _Completions()

    class _Client:
        chat = _Chat()

    monkeypatch.setattr(
        "app.services.content_generation_service._get_openai_client",
        lambda: _Client(),
    )
    out = vision._default_complete("system", [{"type": "text", "text": "x"}])
    assert "ok" in out  # 真正拿到了 content,而非协程对象
