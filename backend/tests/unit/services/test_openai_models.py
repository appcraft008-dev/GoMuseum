"""模型名走配置 + GPT-6 参数差异(4o 系 2027-01-14 退役)。"""

from app.core.config import settings
from app.services.openai_models import VISION, create_kwargs, resolve


def test_defaults_keep_current_models_and_params():
    assert resolve("gpt-4o-mini") == "gpt-4o-mini"
    assert resolve("gpt-4o") == "gpt-4o"
    kw = create_kwargs("gpt-4o-mini", temperature=0, max_tokens=5)
    assert kw == {"model": "gpt-4o-mini", "temperature": 0, "max_tokens": 5}


def test_luna_keeps_temperature_with_effort_none(monkeypatch):
    # Luna 拒收 max_tokens;temperature≠1 只在 effort=none 时允许 —— 闸靠 temperature=0
    monkeypatch.setattr(settings, "OPENAI_FAST_MODEL", "gpt-6-luna")
    kw = create_kwargs("gpt-4o-mini", temperature=0, max_tokens=5)
    assert kw == {
        "model": "gpt-6-luna",
        "temperature": 0,
        "max_completion_tokens": 5,
        "reasoning_effort": "none",
    }


def test_sol_has_no_effort_none_so_temperature_is_dropped(monkeypatch):
    monkeypatch.setattr(settings, "OPENAI_VISION_MODEL", "gpt-6.1-sol")
    kw = create_kwargs(VISION, temperature=0)
    assert kw == {"model": "gpt-6.1-sol", "reasoning_effort": "low"}


def test_tiers_switch_independently(monkeypatch):
    monkeypatch.setattr(settings, "OPENAI_STRONG_MODEL", "gpt-6-luna")
    assert resolve("gpt-4o") == "gpt-6-luna"
    assert resolve("gpt-4o-mini") == "gpt-4o-mini"
    assert resolve(VISION) == "gpt-4o"
    assert resolve("some-other-model") == "some-other-model"


def test_channel_override_beats_tier(monkeypatch):
    monkeypatch.setattr(settings, "LLM_CHANNEL_MODELS", {"gate": "claude-haiku-5-5"})
    assert resolve("gpt-4o-mini", "gate") == "claude-haiku-5-5"
    assert resolve("gpt-4o-mini", "translate") == "gpt-4o-mini"
    assert resolve("gpt-4o-mini") == "gpt-4o-mini"


class _Block:
    def __init__(self, type, text=""):
        self.type, self.text = type, text


class _FakeAnthropic:
    def __init__(self):
        self.calls = []
        self.messages = self

    def create(self, **kw):
        self.calls.append(kw)

        class R:
            content = [_Block("thinking"), _Block("text", "OK"), _Block("text", "!")]

            class usage:
                input_tokens, output_tokens = 11, 3

        return R()


def _claude(monkeypatch, model):
    import app.services.openai_models as om

    fake = _FakeAnthropic()
    monkeypatch.setattr(om, "_anthropic_client", lambda: fake)
    monkeypatch.setattr(settings, "LLM_CHANNEL_MODELS", {"gate": model})
    msgs = [
        {"role": "system", "content": "SYS"},
        {
            "role": "user",
            "content": [
                {"type": "text", "text": "look"},
                {
                    "type": "image_url",
                    "image_url": {"url": "data:image/jpeg;base64,QUJD"},
                },
                {
                    "type": "image_url",
                    "image_url": {"url": "https://x/y.jpg", "detail": "high"},
                },
            ],
        },
    ]
    out = om.chat("gpt-4o-mini", msgs, channel="gate", temperature=0, timeout=30)
    return out, fake.calls[0]


def test_claude_call_drops_temperature_and_disables_thinking_on_haiku(monkeypatch):
    # Claude 5 系拒收 temperature(400);Haiku 关思考写 disabled;只取 text 块
    (text, model, tin, tout), kw = _claude(monkeypatch, "claude-haiku-5-5")
    assert (text, model, tin, tout) == ("OK!", "claude-haiku-5-5", 11, 3)
    assert "temperature" not in kw
    assert kw["thinking"] == {"type": "disabled"}
    assert kw["system"] == "SYS"
    assert kw["timeout"] == 30
    assert kw["messages"] == [
        {
            "role": "user",
            "content": [
                {"type": "text", "text": "look"},
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": "image/jpeg",
                        "data": "QUJD",
                    },
                },
                {"type": "image", "source": {"type": "url", "url": "https://x/y.jpg"}},
            ],
        }
    ]


def test_sonnet_turns_thinking_off_with_between_tools(monkeypatch):
    # Sonnet 5.5 对 disabled 报 400,要 between_tools(10-18 实测)
    _, kw = _claude(monkeypatch, "claude-sonnet-5-5")
    assert kw["thinking"] == {"type": "between_tools"}


def test_openai_path_returns_text_model_and_usage(monkeypatch):
    import app.services.content_generation_service as cgs
    import app.services.openai_models as om

    seen = {}

    class _C:
        class chat:
            class completions:
                @staticmethod
                async def create(**kw):
                    seen.update(kw)

                    class R:
                        class usage:
                            prompt_tokens, completion_tokens = 5, 2

                        choices = [
                            type("c", (), {"message": type("m", (), {"content": "hi"})})
                        ]

                    return R()

    monkeypatch.setattr(cgs, "_get_openai_client", lambda: _C)
    monkeypatch.setattr(settings, "OPENAI_FAST_MODEL", "gpt-6-luna")
    out = om.chat("gpt-4o-mini", [{"role": "user", "content": "x"}], temperature=0)
    assert out == ("hi", "gpt-6-luna", 5, 2)
    assert seen["reasoning_effort"] == "none" and seen["temperature"] == 0
