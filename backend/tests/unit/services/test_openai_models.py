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
