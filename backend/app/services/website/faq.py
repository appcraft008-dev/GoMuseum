"""网站问答页内容(spec 2026-10-31-website-faq)。

内容在 app/content/faq/<城市>/:
- structure.yaml:题目 id、分组、顺序、核对日、复核日、来源、原文摘录、置顶区间、按馆的馆——只写一次;
- text/<语言>.yaml:只放文字,按 id 取。日期/来源不进文字文件,各语言因此不可能不一致。
文字里馆名写占位符 {louvre},渲染时换成该语言馆名;要变格的语言在文字文件 name_forms 里
配好,写 {louvre:gen}(目前只有波兰语的 Luwr)。`review_by`/`evidence` 只用于复核,不上页面。
"""

import argparse
import re
from collections import Counter
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from functools import lru_cache
from pathlib import Path
from zoneinfo import ZoneInfo

import yaml

from app.services.website.data import LANGS, city_slug

FAQ_ROOT = Path(__file__).resolve().parents[2] / "content" / "faq"
_ID = re.compile(r"^[a-z0-9-]+$")
PH = re.compile(r"\{([a-z0-9_]+)(?::([a-z]+))?\}")


@dataclass(frozen=True)
class Part:
    museum: str | None
    checked: date
    review_by: date
    sources: tuple[str, ...]
    evidence: str


@dataclass(frozen=True)
class Item:
    id: str
    group: str
    kind: str  # "rule" | "dated"
    parts: tuple[Part, ...]
    pin_from: date | None
    pin_until: date | None
    link: str | None  # "must_see" | "museum" | None
    skipped: tuple[str, ...] = ()  # 官网没写、明确不答的馆(算已覆盖,不出页面)


@dataclass(frozen=True)
class Faq:
    city: str
    groups: tuple[str, ...]
    items: tuple[Item, ...]
    text: dict[str, dict]


def today() -> date:
    return datetime.now(ZoneInfo("Europe/Paris")).date()


def _part(museum, d: dict) -> Part:
    return Part(
        museum=museum,
        checked=d.get("checked"),
        review_by=d.get("review_by"),
        sources=tuple(d.get("sources") or ()),
        evidence=(d.get("evidence") or "").strip(),
    )


@lru_cache(maxsize=None)
def load_faq(city: str, root: Path | None = None) -> Faq | None:
    base = (root or FAQ_ROOT) / city
    if not (base / "structure.yaml").is_file():
        return None
    st = yaml.safe_load((base / "structure.yaml").read_text(encoding="utf-8"))
    items = []
    for d in st.get("items") or []:
        pm = d.get("per_museum")
        parts = (
            tuple(_part(slug, v) for slug, v in pm.items() if "skip" not in v)
            if pm
            else (_part(None, d),)
        )
        skipped = tuple(slug for slug, v in (pm or {}).items() if "skip" in v)
        items.append(
            Item(
                id=d["id"],
                group=d.get("group", ""),
                kind=d.get("kind", "rule"),
                parts=parts,
                pin_from=d.get("pin_from"),
                pin_until=d.get("pin_until"),
                link=d.get("link"),
                skipped=skipped,
            )
        )
    text = {}
    for p in sorted((base / "text").glob("*.yaml")):
        text[p.stem] = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    return Faq(
        city=city, groups=tuple(st.get("groups") or ()), items=tuple(items), text=text
    )


def faq_languages(faq: Faq) -> list[str]:
    return [lang for lang in LANGS if lang in faq.text]


def is_stale(part: Part, today: date) -> bool:
    return today > part.review_by


def visible(item: Item, today: date) -> bool:
    """时令题全部过了复核日就整条隐藏;长期规则题过期仍显示(带横幅)。"""
    return item.kind != "dated" or not all(is_stale(p, today) for p in item.parts)


def _pinned(item: Item, today: date) -> bool:
    return bool(item.pin_from and item.pin_from <= today <= item.pin_until)


def arrange(faq: Faq, today: date) -> tuple[list[Item], list[tuple[str, list[Item]]]]:
    shown = [i for i in faq.items if visible(i, today)]
    pinned = [i for i in shown if _pinned(i, today)]
    groups = []
    for g in faq.groups:
        items = [i for i in shown if i.group == g and not _pinned(i, today)]
        if items:
            groups.append((g, items))
    return pinned, groups


def expiring(faq: Faq, today: date, days: int):
    until = today + timedelta(days=days)
    rows = [
        (i.id, p.museum, p.review_by, p.sources)
        for i in faq.items
        for p in i.parts
        if p.review_by and p.review_by <= until
    ]
    return sorted(rows, key=lambda r: r[2])


def museums_for_city(city: str) -> list[str]:
    """museums.yaml 里属于该城市的全部馆(含未上线的;上线状态在 DB,运行时另行过滤)。"""
    from app.services.enrichment.catalog import MuseumCatalog
    from app.services.enrichment.factory import CATALOG_PATH

    return [
        slug
        for slug, cfg in MuseumCatalog.from_file(CATALOG_PATH).items()
        if city_slug(cfg.city_en) == city
    ]


def _strings(entry) -> list[str]:
    a = entry.get("a")
    out = [entry.get("q") or "", entry.get("applies_to") or ""]
    out += list(a.values()) if isinstance(a, dict) else [a or ""]
    return out


def _placeholders(entry) -> Counter:
    """按出现次数计:译文少提一次馆名也算不一致。"""
    return Counter(m for s in _strings(entry) for m, _ in PH.findall(str(s)))


def _missing_forms(entry, forms: dict) -> set[str]:
    return {
        f"{{{m}:{case}}}"
        for s in _strings(entry)
        for m, case in PH.findall(str(s))
        if case and case not in forms.get(m, {})
    }


def validate(faq: Faq) -> list[str]:
    errs: list[str] = []
    if "en" not in faq.text:
        return [f"{faq.city}: missing text/en.yaml"]
    slugs = {p.museum for i in faq.items for p in i.parts if p.museum}
    slugs |= {m for i in faq.items for m in i.skipped}
    ids = [i.id for i in faq.items]
    if len(set(ids)) != len(ids):
        errs.append(f"duplicate item ids: {ids}")
    anchors = set()
    for i in faq.items:
        if not _ID.match(i.id):
            errs.append(f"{i.id}: id must match [a-z0-9-]+")
        if i.group not in faq.groups:
            errs.append(f"{i.id}: unknown group {i.group}")
        if i.kind not in ("rule", "dated"):
            errs.append(f"{i.id}: kind must be rule or dated")
        if (i.pin_from is None) != (i.pin_until is None):
            errs.append(f"{i.id}: pin_from and pin_until must come together")
        for p in i.parts:
            who = f"{i.id}/{p.museum}" if p.museum else i.id
            anchor = f"{i.id}-{p.museum.replace('_', '-')}" if p.museum else i.id
            if anchor in anchors:
                errs.append(f"{who}: duplicate anchor {anchor}")
            anchors.add(anchor)
            if not p.sources or not all(s.startswith("https://") for s in p.sources):
                errs.append(f"{who}: needs at least one https:// source")
            if not p.evidence:
                errs.append(f"{who}: evidence is empty")
            if not isinstance(p.checked, date) or not isinstance(p.review_by, date):
                errs.append(f"{who}: checked/review_by must be dates")
            elif p.review_by < p.checked:
                errs.append(f"{who}: review_by before checked")
    en_items = faq.text["en"].get("items") or {}
    for lang, t in faq.text.items():
        if lang not in LANGS:
            errs.append(f"text/{lang}.yaml: unknown language")
            continue
        if set((t.get("groups") or {})) != set(faq.groups):
            errs.append(f"{lang}: group titles must be exactly {list(faq.groups)}")
        for key in ("title", "intro"):
            if not t.get(key):
                errs.append(f"{lang}: missing {key}")
        items = t.get("items") or {}
        for extra in set(items) - set(ids):
            errs.append(f"{lang}: unknown item {extra}")
        for i in faq.items:
            e = items.get(i.id)
            if not e:
                errs.append(f"{lang}: missing item {i.id}")
                continue
            if not e.get("q"):
                errs.append(f"{lang}: {i.id} missing q")
            if (i.kind == "dated") != bool(e.get("applies_to")):
                errs.append(f"{lang}: {i.id} applies_to required only for dated items")
            a = e.get("a")
            museums = {p.museum for p in i.parts if p.museum}
            if museums or i.skipped:
                got = set(a) if isinstance(a, dict) else set()
                for m in museums ^ got:
                    errs.append(f"{lang}: {i.id} answer museums differ at {m}")
                if isinstance(a, dict) and not all(a.values()):
                    errs.append(f"{lang}: {i.id} has an empty museum answer")
            elif not isinstance(a, str) or not a.strip():
                errs.append(f"{lang}: {i.id} answer must be non-empty text")
            for missing in sorted(_missing_forms(e, t.get("name_forms") or {})):
                errs.append(f"{lang}: {i.id} {missing} has no name_forms entry")
            ph = _placeholders(e)
            for unknown in set(ph) - slugs - set(museums_for_city(faq.city)):
                errs.append(f"{lang}: {i.id} unknown placeholder {{{unknown}}}")
            if lang != "en" and i.id in en_items:
                en_ph = _placeholders(en_items[i.id])
                for m in sorted(m for m in set(ph) | set(en_ph) if ph[m] != en_ph[m]):
                    errs.append(f"{lang}: {i.id} placeholder {{{m}}} differs from en")
    return errs


def _main():
    ap = argparse.ArgumentParser(description="列出快到复核日的 FAQ 条目")
    ap.add_argument("--city", default="paris")
    ap.add_argument("--expiring", type=int, default=30, metavar="DAYS")
    args = ap.parse_args()
    faq = load_faq(args.city)
    if not faq:
        raise SystemExit(f"no FAQ for {args.city}")
    for item_id, museum, review_by, sources in expiring(faq, today(), args.expiring):
        print(f"{review_by}\t{item_id}\t{museum or '-'}\t{' '.join(sources)}")


if __name__ == "__main__":
    _main()
