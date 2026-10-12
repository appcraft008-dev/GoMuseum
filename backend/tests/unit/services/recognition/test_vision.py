"""识别器:一次 GPT 视觉调用给候选名(查询非答案,R1)+顺带转写可见文字;label 模式纯转写。
complete 注入离线测。spec 2026-07-03-recognition-design。"""

import io
import json

from app.services.recognition.vision import _shrink, identify


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
    assert out == {
        "candidates": [],
        "label_text": None,
        "self_confidence": "low",
        "pick": None,
    }


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


def test_shrink_reduces_large_image_to_1024():
    from PIL import Image

    buf = io.BytesIO()
    Image.new("RGB", (3000, 2000)).save(buf, format="JPEG")
    big = buf.getvalue()
    small = _shrink(big)
    assert len(small) < len(big)
    out = Image.open(io.BytesIO(small))
    assert max(out.size) == 1024


def test_shrink_garbage_returns_unchanged():
    assert _shrink(b"not an image") == b"not an image"


def test_label_mode_extracts_printed_title_and_artist():
    """墙签动辄几十行(双语说明),整段逐行模糊匹配 prod 要十几分钟(2026-10-06 真机)。
    转写时顺手摘出墙签上**印着的**标题/作者,匹配只拿它们当探针;不许猜。"""
    seen = {}

    def fake(system, user_content):
        seen["system"] = system
        return json.dumps(
            {
                "candidates": [
                    {"title": "L'Air du soir", "artist": "Henri-Edmond Cross"}
                ],
                "label_text": "Henri-Edmond Cross\nL'Air du soir\nVers 1893",
            }
        )

    out = identify("b64data", mode="label", complete=fake)
    s = seen["system"].lower()
    assert "title" in s and "printed" in s and "not guess" in s
    assert out["candidates"] == [
        {
            "title": "L'Air du soir",
            "original_title": None,  # 墙签只印一种语言时没有原文标题
            "artist": "Henri-Edmond Cross",
        }
    ]


def test_original_title_passed_through():
    raw = json.dumps(
        {
            "candidates": [
                {
                    "title": "The Evening Air",
                    "original_title": "L'Air du soir",
                    "artist": "Henri-Edmond Cross",
                }
            ],
            "label_text": None,
            "self_confidence": "medium",
        }
    )
    out = identify("b64", complete=lambda s, u: raw)
    assert out["candidates"][0]["original_title"] == "L'Air du soir"


def test_prompts_ask_for_original_title():
    from app.services.recognition.vision import _ARTWORK_SYSTEM, _LABEL_SYSTEM

    assert "original_title" in _ARTWORK_SYSTEM and "original_title" in _LABEL_SYSTEM


def test_label_mode_uses_gpt4o_high_detail(monkeypatch):
    # 10-07 staging A/B(同一张双语墙签各 5 次):gpt-4o-mini 5/5 把说明文字里提到的
    # 《Luxe, calme et volupté》当主标题;gpt-4o 0/5,且单价几乎相同(mini 图片按 33 倍计 token)
    from app.services.recognition import vision

    seen = []

    def fake(system, user_content, model="gpt-4o-mini"):
        seen.append((model, user_content[0]["image_url"].get("detail")))
        return '{"candidates": [], "label_text": null}'

    monkeypatch.setattr(vision, "_default_complete", fake)
    vision.identify("b64", mode="label")
    vision.identify("b64", mode="artwork")
    assert seen == [("gpt-4o", "high"), ("gpt-4o-mini", None)]


# ---- P1-7(10-12):向量低分时 AI 在向量前 5 名里选 ----

_SHORT = [
    {"title": "Olympia", "artist": "Édouard Manet", "thumb_b64": "T1"},
    {"title": "The Ray", "artist": "Chardin", "thumb_b64": None},
]


def test_shortlist_sent_as_numbered_list_with_reference_images():
    seen = {}

    def fake(system, user_content):
        seen["system"], seen["content"] = system, user_content
        return json.dumps({"candidates": [], "pick": 2})

    out = identify("b64data", complete=fake, shortlist=_SHORT)
    texts = " ".join(c["text"] for c in seen["content"] if c["type"] == "text")
    assert "1. Olympia — Édouard Manet" in texts and "2. The Ray — Chardin" in texts
    urls = [c["image_url"]["url"] for c in seen["content"] if c["type"] == "image_url"]
    assert urls == ["data:image/jpeg;base64,b64data", "data:image/jpeg;base64,T1"]
    assert "pick" in seen["system"]
    assert out["pick"] == 2


def test_pick_out_of_range_or_garbage_is_none():
    for raw in [0, 3, "x", None, "null"]:
        out = identify(
            "b64data",
            complete=lambda s, u, raw=raw: json.dumps({"candidates": [], "pick": raw}),
            shortlist=_SHORT,
        )
        assert out["pick"] is None, raw


def test_no_shortlist_no_pick_and_prompt_unchanged():
    seen = {}

    def fake(system, user_content):
        seen["system"] = system
        return json.dumps({"candidates": [], "pick": 1})

    out = identify("b64data", complete=fake)
    assert out["pick"] is None
    assert "pick" not in seen["system"]
