"""讲解文本**质量**体检(区别于 coverage_report 的"有没有")。

为什么需要:此前衡量内容只有两把尺子 —— 覆盖率(生成了多少段)和过闸率
(多少段通过接地闸)。两把都对质量失明:

  接地闸的判定规则里写着「引导句/观察句:无具体可证伪事实 → keep=True」——
  **套话不陈述事实,所以永远过闸**。于是 2026-09-13 实测:prod 上 guide 段
  63.8% 以 "take a moment to really look…" 开头,282 段只有 38 种开头,
  而过闸率一路绿灯,25635 段里没人发现。

本脚本把三件闸看不见的事变成数字:

  ① 开头多样性  前 N 词的唯一率。低 = 模板化(同一个骨架被填成同一套措辞)。
  ② 跨作品 n-gram  同一短语出现在多少件**不同**作品里。高 = 万能句。
     这是套话最硬的判据:一个短语若能安在 80% 的作品上,它必然不携带信息。
  ③ 事实锚点密度  含年份/数字/专有名词的句子占比。低 = 空洞评价句多。

⚠️ 三个都是**相对**指标,没有绝对合格线。用法是同一批件改动前后对比
(prompt A/B),或同一段不同馆横比。给它们拍阈值会重犯
「没有正样本校准的阈值会越收越紧」那个错。

⚠️ 锚点率**系统性偏低**:句首的专有名词不算锚点(见 anchor_rate 注释),
所以 "Proudhon defended him in print." 这种明明具体的句子会被漏掉。
这是为了不把 "Paintings can be moving." 也判成有锚点而付的代价。
对 A/B 无影响(两侧同一把尺子),但看到绝对值偏低时别去调规则。

用法:
    python scripts/text_quality_report.py                      # 全部馆
    python scripts/text_quality_report.py --museum louvre --lang en
    python scripts/text_quality_report.py --section guide --top-ngrams 25
"""

from __future__ import annotations

import argparse
import collections
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.database import SessionLocal  # noqa: E402
from app.models.content import ObjectContentSection  # noqa: E402
from app.models.museum import Museum  # noqa: E402
from app.models.museum_object import MuseumObject  # noqa: E402

_WORD = re.compile(r"[a-z']+")
_SENT = re.compile(r"(?<=[.!?])\s+")
_YEAR = re.compile(r"\b1[0-9]{3}\b|\b20[0-9]{2}\b")
_NUM = re.compile(r"\b\d+(?:\.\d+)?\s*(?:cm|mm|m|kg)\b|\b\d{2,}\b")
_PROPER = re.compile(r"^[A-Z][a-z]{2,}")
_MIN_SENT_WORDS = 4  # 更短的多是片段/标点残渣,计入会稀释锚点率


def _words(text: str) -> list[str]:
    return _WORD.findall((text or "").lower())


def banned_phrase_rate(bodies: list[str]) -> tuple[int, int]:
    """(含黑名单套话的段数, 总段数)。黑名单从 prompts 导入 —— **同一份**。

    手抄一份到这里就会漂移:prompt 禁了 A,报告查的是 B,两边都"通过"。
    """
    from app.services.enrichment.prompts import BANNED_PHRASES

    hits = sum(1 for b in bodies if b and any(p in b.lower() for p in BANNED_PHRASES))
    return hits, len([b for b in bodies if b])


def head_diversity(bodies: list[str], n: int = 6) -> tuple[int, int, list]:
    """(不同开头数, 段数, 最常见开头 top3)。开头 = 前 n 个词。"""
    heads = collections.Counter(" ".join(_words(b)[:n]) for b in bodies if b)
    total = sum(heads.values())
    return len(heads), total, heads.most_common(3)


def cross_work_ngrams(rows: list[tuple], n: int = 5, top: int = 20) -> list:
    """[(命中作品数, n-gram)]，按命中作品数降序。rows = [(qid, body)]。

    计的是**不同作品**而不是出现次数 —— 一件作品里重复十次只算一件,
    否则长文本会自己刷高排名,掩盖真正的跨作品套话。
    """
    seen: dict = collections.defaultdict(set)
    for qid, body in rows:
        w = _words(body)
        for i in range(len(w) - n + 1):
            seen[" ".join(w[i : i + n])].add(qid)
    return sorted(((len(q), g) for g, q in seen.items()), reverse=True)[:top]


def anchor_rate(bodies: list[str]) -> tuple[int, int]:
    """(含具体锚点的句数, 总句数)。锚点 = 年份 / 数字 / 非句首专有名词。

    专有名词取**句首之外**的大写词:句首大写是语法,不是信息。
    """
    anchored = total = 0
    for b in bodies:
        for sent in _SENT.split(b or ""):
            parts = sent.split()
            if len(parts) < _MIN_SENT_WORDS:
                continue
            total += 1
            if (
                _YEAR.search(sent)
                or _NUM.search(sent)
                or any(_PROPER.match(w) for w in parts[1:])
            ):
                anchored += 1
    return anchored, total


def report(rows_by_section: dict, top_ngrams: int) -> None:
    """rows_by_section: {section_code: [(qid, body)]}"""
    print(
        "%-16s %6s %8s %10s %12s %10s"
        % ("段", "段数", "作品数", "开头多样性", "事实锚点率", "套话命中")
    )
    print("-" * 72)
    for sec in sorted(rows_by_section, key=lambda s: -len(rows_by_section[s])):
        rows = rows_by_section[sec]
        bodies = [b for _, b in rows]
        uniq, total, top3 = head_diversity(bodies)
        a, t = anchor_rate(bodies)
        bh, bt = banned_phrase_rate(bodies)
        print(
            "%-16s %6d %8d %9.0f%% %11.1f%% %9.0f%%"
            % (
                sec,
                total,
                len({q for q, _ in rows}),
                100.0 * uniq / max(total, 1),
                100.0 * a / max(t, 1),
                100.0 * bh / max(bt, 1),
            )
        )
    for sec in sorted(rows_by_section, key=lambda s: -len(rows_by_section[s])):
        rows = rows_by_section[sec]
        works = len({q for q, _ in rows})
        grams = cross_work_ngrams(rows, top=top_ngrams)
        if not grams or grams[0][0] < 2:
            continue
        print(f"\n=== {sec}: 跨作品最高频 5-gram(分母 {works} 件) ===")
        for cnt, g in grams:
            if cnt < 2:
                break
            print("  %4d 件 (%5.1f%%)  %s" % (cnt, 100.0 * cnt / works, g))
        uniq, total, top3 = head_diversity([b for _, b in rows])
        print(f"  — 最常见开头({total} 段):")
        for h, c in top3:
            print('      %4d 次 (%5.1f%%)  "%s…"' % (c, 100.0 * c / total, h))


def load(db, museum: str | None, lang: str, section: str | None, limit: int) -> dict:
    q = (
        db.query(
            MuseumObject.qid,
            ObjectContentSection.section_code,
            ObjectContentSection.body,
        )
        .join(ObjectContentSection, ObjectContentSection.object_id == MuseumObject.id)
        .filter(
            ObjectContentSection.language == lang,
            ObjectContentSection.status == "published",
            ObjectContentSection.body.isnot(None),
        )
    )
    if museum:
        m = db.query(Museum).filter_by(slug=museum).one_or_none()
        if m is None:
            raise SystemExit(f"museum not found: {museum}")  # typo 别静默 0 段
        q = q.filter(MuseumObject.museum_id == m.id)
    if section:
        q = q.filter(ObjectContentSection.section_code == section)
    out: dict = collections.defaultdict(list)
    for qid, code, body in q.limit(limit).all():
        if body and body.strip():
            out[code].append((qid, body))
    return dict(out)


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--museum", help="馆 slug(默认全部)")
    p.add_argument("--lang", default="en")
    p.add_argument("--section", help="只看某段")
    p.add_argument("--limit", type=int, default=5000)
    p.add_argument("--top-ngrams", type=int, default=20)
    a = p.parse_args()
    db = SessionLocal()
    try:
        rows = load(db, a.museum, a.lang, a.section, a.limit)
    finally:
        db.close()
    if not rows:
        raise SystemExit("没有匹配的已发布段")
    print(f"语言 {a.lang}" + (f" / 馆 {a.museum}" if a.museum else " / 全部馆") + "\n")
    report(rows, a.top_ngrams)


if __name__ == "__main__":
    main()
