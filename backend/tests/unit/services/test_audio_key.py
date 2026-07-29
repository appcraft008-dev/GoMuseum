"""音频 key 必须不可推测——付费墙建在语音上的技术前提。"""

import re

from app.services.content_repo import audio_key


def test_key_is_not_guessable_from_qid():
    # 旧格式 object-audio/{qid}/{lang}/{section}.mp3 可直接拼出 → 绕过一切鉴权
    # (2026-07-27 实测无鉴权 HTTP 200 拿到完整音频)
    k = audio_key("object-audio", "Q12418", "zh", "guide")
    assert k.startswith("object-audio/Q12418/zh/guide-")
    assert k != "object-audio/Q12418/zh/guide.mp3"  # 不是旧的可推测格式
    assert k.endswith(".mp3")


def test_two_calls_differ():
    a = audio_key("object-audio", "Q1", "zh", "guide")
    b = audio_key("object-audio", "Q1", "zh", "guide")
    assert a != b, "随机后缀必须每次不同,否则仍可推测"


def test_suffix_has_enough_entropy():
    # ⚠️ 别用 rsplit("-") 反解后缀:token_urlsafe 的字母表**含 `-`**,
    # 随机串里出现一个就把后缀截短 → 测试 ~22% 概率假红(实测踩到)。
    # 按已知前缀切,才是真的后缀。
    prefix = "object-audio/Q1/zh/guide-"
    k = audio_key("object-audio", "Q1", "zh", "guide")
    suffix = re.sub(r"\.mp3$", "", k)[len(prefix) :]
    assert len(suffix) >= 16, f"后缀太短易爆破: {suffix}"
