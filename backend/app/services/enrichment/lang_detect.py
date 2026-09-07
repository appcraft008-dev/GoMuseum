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
            # 简繁互串:**必须跑在短文本豁免之前**。豁免存在的理由是"统计判别
            # 在短文本上不可靠",而简繁是逐字查表、与长度无关;而且实际漏出来的
            # 372 条标题、106 个作者名全是短文本 —— 放在豁免之后等于不设防。
            if lang in ("zh", "zh-hant") and not _han_script_ok(t, lang):
                return False
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


# ---- 简繁判别(zh vs zh-hant) ----
# 上面 _NONLATIN_SCRIPT 里 zh 和 zh-hant 共用同一条 [一-鿿]:能挡"英文混进
# 中文位",**挡不住简繁互串** —— 两者码位都在汉字区。prod 实测漏出来的量
# (2026-09-07):繁体标题 372/27132、作者名 106/4183、正文 82/2659、
# 问答 31/1123、作者简介 17/191。典型形态不是整段简体,而是繁体正文里漏出
# 个别简体字(「蘇薩廢墟全景图」的「图」应作「圖」)。

_CC: dict[str, object] = {}
_simp_only: dict[str, list[str]] | None = None


def _cc(config: str):
    if config not in _CC:
        from opencc import OpenCC

        _CC[config] = OpenCC(config)
    return _CC[config]


def _opencc_dict(name: str) -> dict[str, list[str]]:
    """读 opencc 自带字表(制表符分隔:源字 → 空格分隔的候选)。"""
    import os

    import opencc

    path = os.path.join(os.path.dirname(opencc.__file__), "dictionary", name)
    out: dict[str, list[str]] = {}
    with open(path, encoding="utf-8") as f:
        for line in f:
            parts = line.rstrip("\n").split("\t")
            if len(parts) == 2 and len(parts[0]) == 1:
                out[parts[0]] = parts[1].split(" ")
    return out


def simplified_only() -> dict[str, list[str]]:
    """简体专有字 → 繁体候选。**从 opencc 自带字表推导,不手工维护**。

    朴素做法(「s2t 转得动就是简体」)在真实语料上误伤 900/2659 篇 —— s2t 会把
    繁体里本来就合法的字也"纠"成另一个写法。两步排掉:

    ① **候选列表含该字自身 → 不算简体专有**。opencc 自己就是这么标歧义的:
       `里→裏 里`、`台→臺 檯 颱 台`、`后→後 后`、`干→幹 乾 干` —— 自身在列
       说明该字在繁体里也合法。真简体字没有自身:`图→圖`、`们→們`、`东→東`。
    ② **再排掉 TWVariantsRev / HKVariantsRev 的键**:台/港标准写法,opencc 偏好
       古体(秘→祕、群→羣、床→牀、峰→峯、痴→癡)。这 5 个字占①之后残留误伤的
       九成(秘 139 篇、群 77、床 32、峰 24、痴 15)。

    两步之后 prod 全量实测:zh 位 0 误伤(2659 篇);zh-hant 位命中 82 篇,抽查全真。

    ⚠️ 字表路径在 opencc 包内部,版本升级可能挪位置 —— 拿不到就返回 {},退化成
    "不判简繁"(与本模块 fail-open 一致)。**靠 test_lang_detect 的非空断言守住**,
    否则这道闸会静默失效而所有测试照绿。
    """
    global _simp_only
    if _simp_only is None:
        try:
            cand = {
                c: v for c, v in _opencc_dict("STCharacters.txt").items() if c not in v
            }
            for name in ("TWVariantsRev.txt", "HKVariantsRev.txt"):
                for c in _opencc_dict(name):
                    cand.pop(c, None)
            _simp_only = cand
        except Exception:
            _simp_only = {}
    return _simp_only


def to_traditional(text: str) -> str:
    """把**简体专有字**换成繁体形,其余一律原样。用于显示名(标题/人名)。

    为什么不直接 `s2t.convert()`:它会顺手把繁体里合法的字也改掉(里→裏、
    台→臺、后→後),那是改写不是纠错。这里拿整串转换的结果、只在**简体专有字
    的位置**采纳 —— 整串转换负责多候选字按词组消歧(发现→發現、头发→頭髮),
    位置过滤负责不该动的字不动。

    对不齐(转换后长度变了)就整串不动:宁可漏,不可乱改用户看得见的名字。
    prod 372 条含简体标题实测 0 条对不齐。
    """
    simp = simplified_only()
    if not text or not simp or not any(c in simp for c in text):
        return text
    conv = _cc("s2t").convert(text)
    if len(conv) != len(text):
        return text
    return "".join(b if a in simp else a for a, b in zip(text, conv))


def _han_script_ok(text: str, lang: str) -> bool:
    """zh 位不许有繁体专有字,zh-hant 位不许有简体专有字。

    zh 侧直接用 t2s:繁体专有字没有歧义(這/國/東 不会出现在简体文里),
    prod 2659 篇实测 0 误伤,不需要 zh-hant 那侧的两步排除。
    """
    try:
        if lang == "zh":
            return _cc("t2s").convert(text) == text
        return not any(c in simplified_only() for c in text)
    except Exception:
        return True  # fail-open,同本模块其它检查
