"""语言一致性检测器:text 是否真的是 lang(散文校验)。离线、确定性。
非拉丁按字形(拉丁残片占比)、拉丁用 lingua。派生自 DEFAULT_LANGUAGES,语言无关。
fail-open:短文本/专名/不确定/异常 → True(放行,宁漏不误杀名字短标题)。"""

import re

# 非拉丁字形语言 → 该字形的 Unicode 判定(加新非拉丁语言加一行)。
_NONLATIN_SCRIPT = {
    "zh": r"[一-鿿]",
    "zh-hant": r"[一-鿿]",
    "ja": r"[一-鿿぀-ヿ]",
    "ko": r"[가-힣]",
}
# 拉丁语言 code → lingua Language 名(候选集派生自 DEFAULT_LANGUAGES 与此交集)。
_LINGUA_CODE = {
    "en": "ENGLISH",
    "fr": "FRENCH",
    "de": "GERMAN",
    "es": "SPANISH",
    "it": "ITALIAN",
    "pl": "POLISH",
}
_LATIN = re.compile(r"[a-zA-Z]")
_detector = None


def _get_detector():
    global _detector
    if _detector is None:
        from lingua import Language, LanguageDetectorBuilder

        from app.services.enrichment.lang_config import DEFAULT_LANGUAGES

        langs = [
            getattr(Language, _LINGUA_CODE[c])
            for c in DEFAULT_LANGUAGES
            if c in _LINGUA_CODE
        ]
        _detector = LanguageDetectorBuilder.from_languages(*langs).build()
    return _detector


def text_in_language(text: str, lang: str) -> bool:
    t = (text or "").strip()
    if not t:
        return True
    try:
        alpha = re.findall(r"[^\W\d_]", t, re.UNICODE)  # 字母类字符
        latin = sum(1 for c in alpha if _LATIN.match(c)) if alpha else 0
        if lang in _NONLATIN_SCRIPT:
            # 非拉丁目标:短(名字/短标题)放行;否则拉丁占比 >40% = 英文污染
            if len(t) < 15:
                return True
            return not alpha or (latin / len(alpha)) <= 0.4
        if lang in _LINGUA_CODE:
            from lingua import Language

            # 拉丁目标但大量非拉丁字母(CJK 等)= 明确不是该语言(如中文进 en 位),
            # 不受短文本豁免(拉丁字段里的 CJK 一定错)。
            if alpha and (latin / len(alpha)) < 0.6:
                return False
            # 拉丁 vs 拉丁:短文本 lingua 不稳 → 放行(名字);否则 lingua 判别
            if len(t) < 15 or len(t.split()) < 3:
                return True
            det = _get_detector()
            conf = det.compute_language_confidence_values(t)
            if not conf:
                return True
            top = conf[0]
            want = getattr(Language, _LINGUA_CODE[lang])
            return not (top.language != want and top.value >= 0.7)
        return True  # 未知/lingua 外语言 → 放行(兜底不崩)
    except Exception:
        return True  # fail-open
