"""识别兜底的 AI 用量要记账(spec §4.1 补记账;B8:原来只取 chat()[0],tokens 丢了)。"""

import pytest

from app.services import llm_usage, openai_models
from app.services.recognition import vision


@pytest.mark.parametrize(
    "mode,channel", [("artwork", "recognition"), ("label", "label")]
)
def test_fallback_usage_recorded_under_its_channel(monkeypatch, mode, channel):
    seen = []
    monkeypatch.setattr(
        openai_models,
        "chat",
        lambda *a, **k: ('{"candidates": []}', "gpt-6-luna", 1200, 80),
    )
    monkeypatch.setattr(llm_usage, "record_llm_usage", lambda *a, **k: seen.append(a))
    vision.identify("aGk=", mode=mode)
    assert seen == [(channel, "gpt-6-luna", 1200, 80)]
