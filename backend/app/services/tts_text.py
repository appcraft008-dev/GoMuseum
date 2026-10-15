"""送 Google TTS 前的切句(spec 2026-10-15 §2.3/§3.1)。

Google 流式合成会**静默吞掉超长句的句尾**(81 字中文句尾 6 字 9/9 次没念,不报错);
只在逗号处切不够 —— Google 按标点把没有句号的 input 拼回一句 —— 切点必须改成句号。
阈值是实测「最长且未被吞」的长度,不是拍的。
"""

import re

_CJK = {"zh", "zh-hant", "ja", "ko"}
_MAX = {"zh": 60, "zh-hant": 60, "ja": 95, "ko": 95}
_DEFAULT_MAX = 270
_MIN_LATIN = 12  # 更短的拉丁碎块多半是缩写断出来的,并入下一句

# 句末:CJK 句末标点后;拉丁 .!? 后跟空白(排除省略号);换行
_SENT_END = re.compile(r"(?<=[。！？])|(?<=[.!?])(?<!\.\.\.)\s+")
_LINES = re.compile(r"\n+")  # 换行处必断,且各行单独补句号(不跨行合并)
_LEAD_CLOSERS = re.compile(r"^[」』”’）)\]\"']+")
_WORD = re.compile(r"\w")
_CLAUSE = re.compile(r"(?<=[，；：、,;:])")
_ABBR_END = re.compile(r"\b[A-Z][a-z]{0,2}\.$")  # St. / Mme. / Dr. / Vve.
_CLAUSE_MARKS = "，；：、,;:"
_END_MARKS = "。！？.!?"


def split_sentences(text: str, language: str) -> list[str]:
    limit = _MAX.get(language, _DEFAULT_MAX)
    cjk = language in _CJK
    stop = "。" if cjk else "."
    out: list[str] = []
    for line in _LINES.split(text or ""):
        raw = [s.strip() for s in _SENT_END.split(line) if s and s.strip()]
        raw = _attach_punctuation(raw)
        if not cjk:
            raw = _merge_fragments(raw)
        for s in raw:
            out.extend(_split_long(s, limit, stop, cjk))
    # 每句都要有句末标点:没句号的 input 会被 Google 拼进下一句,长了就吞句尾
    return [_close(s, stop) for s in out]


def _attach_punctuation(parts: list[str]) -> list[str]:
    """「好。」 的 」、「真的吗？！」 的 ！ 这类切出来的纯标点/前导收尾符并回前一句;
    纯标点且没有前一句的直接丢(不发空 input)。"""
    out: list[str] = []
    for p in parts:
        lead = _LEAD_CLOSERS.match(p)
        if lead and out:
            out[-1] += lead.group(0)
            p = p[lead.end() :].strip()
        if not _WORD.search(p):
            if out and p:
                out[-1] += p
            continue
        out.append(p)
    return out


def _merge_fragments(parts: list[str]) -> list[str]:
    out: list[str] = []
    carry = ""
    for p in parts:
        cur = f"{carry} {p}".strip() if carry else p
        if len(cur) < _MIN_LATIN or _ABBR_END.search(cur):
            carry = cur
            continue
        out.append(cur)
        carry = ""
    if carry:
        out.append(carry)
    return out


def _split_long(s: str, limit: int, stop: str, cjk: bool) -> list[str]:
    if len(s) <= limit:
        return [s]
    room = limit - 1  # 给 _close 补的句号留一位
    chunks: list[str] = []
    cur = ""
    for p in _CLAUSE.split(s):
        while len(p) > room:  # 一段里没有可切的逗号:硬切
            if cur:
                chunks.append(cur)
                cur = ""
            space = -1 if cjk else p.rfind(" ", 0, room)
            cut = space if space > 0 else room
            chunks.append(p[:cut])
            p = p[cut:]
        if cur and len(cur) + len(p) > room:
            chunks.append(cur)
            cur = ""
        cur += p
    if cur:
        chunks.append(cur)
    return [_close(c, stop) for c in (c.strip() for c in chunks) if c]


def _close(c: str, stop: str) -> str:
    if c[-1] in _CLAUSE_MARKS:
        return c[:-1] + stop
    if c.rstrip("」』”’）)]\"'")[-1:] in tuple(_END_MARKS):  # 「好。」 已有句号
        return c
    return c + stop
