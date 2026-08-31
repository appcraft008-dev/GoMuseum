"""目标翻译语言集配置：全局默认 + museums.yaml 覆盖，代码零硬编码语言。spec §14。"""

from __future__ import annotations

# 默认语言集是运营旋钮、非架构（spec §14）。主市场欧洲 + 中文（开发语言）。
DEFAULT_LANGUAGES = ["en", "fr", "de", "es", "it", "zh", "pl", "ja", "ko", "zh-hant"]

# 语言 code → 英文名（喂翻译/校验 prompt，便于模型识别目标语言）。
LANG_NAMES = {
    "en": "English",
    "fr": "French",
    "de": "German",
    "es": "Spanish",
    "it": "Italian",
    "zh": "Chinese",
    "pl": "Polish",
    "ja": "Japanese",
    "ko": "Korean",
    "zh-hant": "Traditional Chinese",
}


# 模型偶尔会在译文开头回贴语言标签("Polish:\n…"、"Italiano: …")。
# 剥离时要认的不只是 LANG_NAMES 的英文名,还有各语言的**本地自称** ——
# 实测两种都出现过,而且同一语言两种混用。
_NATIVE_LANG_NAMES = (
    "Italiano Deutsch Fran\u00e7ais Francais Espa\u00f1ol Espanol Polski "
    "Portugu\u00eas \u65e5\u672c\u8a9e \ud55c\uad6d\uc5b4 \u4e2d\u6587 "
    "\u7e41\u9ad4\u4e2d\u6587 \u7b80\u4f53\u4e2d\u6587 English"
).split()


def strip_language_label(text: str) -> str:
    """剥掉译文开头被模型回贴的语言标签。

    ⚠️ 根因是**翻译 prompt 的输入格式自己在诱导**:user 消息写成
    `English:\n{原文}`,模型照猫画虎输出 `Polish:\n{译文}`。system 里那句
    "Return ONLY the translated text" 拦不住 —— 格式示范比指令更强。
    实测 prod 存量 **1088 段**带这种前缀(pl 289 / it 267 / de 144 …),
    涉及 900+ 件作品,而**两道闸都抓不到**:忠实度闸看内容(前缀不改事实)、
    语言检测闸看正文语种(是对的)。**形式缺陷得有形式检查。**

    只剥"已知语言名 + 冒号 + 行首"这一种形态,不做通用的"短词加冒号"剥离 ——
    正文可能合法地以某个词加冒号开头,误伤比漏网糟。
    """
    import re

    names = set(LANG_NAMES.values()) | set(_NATIVE_LANG_NAMES)
    alt = "|".join(sorted((re.escape(n) for n in names), key=len, reverse=True))
    # 语言名后允许一个括号补充(实测存量有「中文（繁體）：」),冒号前允许空格
    # (法式排版「Français :」)。
    return re.sub(
        rf"^[ \t]*(?:{alt})[ \t]*(?:[（(][^）)]{{0,10}}[）)])?[ \t]*[:\uff1a][ \t]*\r?\n?",
        "",
        text or "",
        count=1,
    )


def resolve_languages(override: list[str] | None = None) -> list[str]:
    """解析目标语言集：有非空 override（来自 museums.yaml）用之，否则全局默认。"""
    return list(override) if override else list(DEFAULT_LANGUAGES)
