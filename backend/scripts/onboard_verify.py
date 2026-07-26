"""上新馆验收闸(2026-07-26,卢浮宫六坑固化)。

契约里的教训是文字,会被跳过;这里把它们变成**跑得起来的检查**。
每项对应一类真实事故,红了就给出补救命令。上新馆最后一步:全绿才算上完。

用法(容器内):
  python scripts/onboard.py <slug> verify --target prod [--json]
"""

from __future__ import annotations

import re

from app.models.artist import Artist
from app.models.museum import Museum
from app.models.museum_object import MuseumObject, ObjectImage

# 合法 Wikidata QID;其余(blank node genid hex / 合成把手)都不该出现在 artist_qid
_QNUM = re.compile(r"^Q\d+$")


def _pct(n: int, d: int) -> float:
    return 100.0 * n / d if d else 100.0


def _check(name, ok, detail, fix=None) -> dict:
    return {"name": name, "ok": bool(ok), "detail": detail, "fix": fix}


def build_checks(db, slug: str, langs: list[str]) -> dict:
    """跑全部验收项。返回 {"slug","checks":[...],"passed":bool}。只读,不改数据。"""
    m = db.query(Museum).filter_by(slug=slug).one_or_none()
    if not m:
        return {
            "slug": slug,
            "checks": [_check("馆存在", False, "unknown museum")],
            "passed": False,
        }

    rows = (
        db.query(
            MuseumObject.qid,
            MuseumObject.title_en,
            MuseumObject.artist_en,
            MuseumObject.attributes,
        )
        .filter_by(museum_id=m.id)
        .all()
    )
    total = len(rows)
    checks: list[dict] = []

    checks.append(
        _check(
            "目录非空",
            total > 0,
            f"archive={total}",
            f"python scripts/onboard.py {slug} catalog --target <env>",
        )
    )
    if not total:
        return {"slug": slug, "checks": checks, "passed": False}

    # ① 各语言译名覆盖(names 漏跑/半途崩 → 列表大面积外文)
    worst_lang, worst_pct = (langs[0] if langs else "-"), 100.0
    for lg in langs:
        n = sum(
            1 for _q, _t, _a, at in rows if ((at or {}).get("title_i18n") or {}).get(lg)
        )
        p = _pct(n, total)
        if p <= worst_pct:  # <= 保证全 100% 时也报出一个真实语言名,不显 None
            worst_lang, worst_pct = lg, p
    checks.append(
        _check(
            "各语言译名覆盖 ≥95%",
            worst_pct >= 95,
            f"最低 {worst_lang}={worst_pct:.1f}%",
            f"python scripts/onboard.py {slug} names --target <env> --use-batch",
        )
    )

    # ② 标题空值(title_en 只读列的对称性事故:9497 件英文标题空白)
    no_title = sum(
        1
        for _q, ten, _a, at in rows
        if not (((at or {}).get("title_i18n") or {}).get("en") or ten)
    )
    checks.append(
        _check(
            "英文标题空值 <1%",
            _pct(no_title, total) < 1,
            f"{no_title}/{total} 无英文标题",
            f"python scripts/onboard.py {slug} names --target <env> --use-batch",
        )
    )

    # ③ 作者本地化(batch 路径漏 P170 事故:10041 件作者名显拉丁)
    aqids = {aq for _q, _t, _a, at in rows if (aq := (at or {}).get("artist_qid"))}
    with_artist = sum(
        1 for _q, _t, aen, at in rows if (at or {}).get("artist_qid") or aen
    )
    if aqids:
        arts = {a.qid: a for a in db.query(Artist).filter(Artist.qid.in_(list(aqids)))}
        localized = sum(
            1 for aq in aqids if (arts.get(aq) and (arts[aq].name_i18n or {}).get("zh"))
        )
        p = _pct(localized, len(aqids))
    else:
        p = 0.0
    checks.append(
        _check(
            "作者中文名 ≥90%(有作者身份的)",
            p >= 90 if aqids else with_artist == 0,
            f"{p:.1f}%({len(aqids)} 位作者;{with_artist} 件有作者)",
            f"python scripts/onboard.py {slug} names --target <env> --use-batch",
        )
    )

    # ④ artist_qid 格式(blank node genid 假身份事故:4642 件古物中招)
    bad = [aq for aq in aqids if not _QNUM.match(aq)]
    checks.append(
        _check(
            "artist_qid 格式全合法",
            not bad,
            f"非法 {len(bad)} 个" + (f",样例 {bad[:2]}" if bad else ""),
            "python scripts/clean_blank_node_artists.py --apply",
        )
    )

    # ⑤ 图物化与嵌入(credit 超列宽崩掉整轮的事故会让这里缺口很大)
    img_rows = (
        db.query(ObjectImage)
        .join(MuseumObject, MuseumObject.id == ObjectImage.object_id)
        .filter(MuseumObject.museum_id == m.id)
    )
    img_total = img_rows.count()
    img_done = img_rows.filter(ObjectImage.image_key.isnot(None)).count()
    pending = img_rows.filter(
        ObjectImage.image_key.is_(None), ObjectImage.source_url.isnot(None)
    ).count()
    checks.append(
        _check(
            "图物化无残留",
            pending == 0,
            f"已物化 {img_done}/{img_total},待物化 {pending}",
            f"python scripts/onboard.py {slug} images --target <env>",
        )
    )

    # ⑥ 门面:介绍与封面(上新馆配方最后一步漏跑的常见项)
    di = m.description_i18n or {}
    checks.append(
        _check(
            "馆介绍已生成且分段",
            bool(di.get("en")) and "\n\n" in (di.get("en") or ""),
            f"语言数 {len(di)};en 段落 {(di.get('en') or '').count(chr(10) * 2) + 1}",
            f"python scripts/onboard.py {slug} intro --target <env>",
        )
    )
    checks.append(
        _check(
            "封面已选",
            bool(m.cover_image_key),
            str(m.cover_image_key),
            f"python scripts/onboard.py {slug} intro --target <env> --force",
        )
    )

    # ⑦ 门面响应耗时:规模会让"本来没问题"的设计失效(纪律⑧)。馆包全量曾 8.2s/5MB,
    # 而 App 只要门面字段——这里量的就是 App 实际拿的那份,涨上去立刻红。
    import time as _t

    from app.services.museum_repo import get_museum_pack

    t0 = _t.time()
    get_museum_pack(db, slug, artworks=False)
    facade_ms = int((_t.time() - t0) * 1000)
    checks.append(
        _check(
            "门面响应 <1s",
            facade_ms < 1000,
            f"{facade_ms}ms(App 拿的是 artworks=false 那份)",
            "查是否又有全量加载混进门面路径(纪律⑧:实测别读代码)",
        )
    )

    return {"slug": slug, "checks": checks, "passed": all(c["ok"] for c in checks)}


def print_human(result: dict) -> None:
    print(f"上新馆验收: {result['slug']}")
    for c in result["checks"]:
        mark = "✓" if c["ok"] else "✗"
        print(f"  {mark} {c['name']}: {c['detail']}")
        if not c["ok"] and c.get("fix"):
            print(f"      → 补救: {c['fix']}")
    print("结论:", "全绿,可对外" if result["passed"] else "未通过,见上方补救命令")
