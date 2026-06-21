"""目标翻译语言集配置：全局默认 + museums.yaml 覆盖，代码零硬编码语言。spec §14。"""

from __future__ import annotations

# 默认语言集是运营旋钮、非架构（spec §14）。主市场欧洲 + 中文（开发语言）。
DEFAULT_LANGUAGES = ["en", "fr", "de", "es", "it", "zh"]

# 语言 code → 英文名（喂翻译/校验 prompt，便于模型识别目标语言）。
LANG_NAMES = {
    "en": "English",
    "fr": "French",
    "de": "German",
    "es": "Spanish",
    "it": "Italian",
    "zh": "Chinese",
}


def resolve_languages(override: list[str] | None = None) -> list[str]:
    """解析目标语言集：有非空 override（来自 museums.yaml）用之，否则全局默认。"""
    return list(override) if override else list(DEFAULT_LANGUAGES)
