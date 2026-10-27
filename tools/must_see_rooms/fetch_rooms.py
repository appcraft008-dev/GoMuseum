"""从博物馆官网取必看作品的展厅号,输出可贴回 museums.yaml 的 `must_see:` 片段。

spec 2026-10-27 必看打卡 §五.5。**只读官网,不写任何库**;改清单走 yaml 的 PR。
用法:python tools/must_see_rooms/fetch_rooms.py <slug>
请求要克制:逐件请求、间隔 ≥1 秒、失败不重试(打印成注释交人看)。

官网链接从 Wikidata 取:卢浮宫 P9394(藏品库 id)→ 官方 JSON;橘园/小皇宫取 P973
里对应域名的作品页。奥赛官网拒绝程序访问(403)→ 原样打印,不标位置。
"""

from __future__ import annotations

import html as _html
import json
import re
import sys
import time
import urllib.request
from pathlib import Path

UA = "GoMuseum-must-see-rooms/1.0 (appcraft008@gmail.com)"
YAML = Path(__file__).resolve().parents[2] / "backend" / "museums.yaml"
# 巴黎博物馆集团藏品库的楼层叫法(小皇宫):花园层在地面层之下
_PM_LEVELS = {"rez-de-jardin": -1, "rez-de-chaussée": 0, "rez-de-chaussee": 0}


def _loc(wing=None, level=None, room=None) -> dict | None:
    if wing is None and level is None and not room:
        return None
    return {"wing": wing, "level": level, "room": room or None}


def parse_louvre(d: dict) -> dict | None:
    """`room` 形如 "Salle 711, Aile Aile Denon, Niveau 1";空串 = 官网没给位置。"""
    room = (d.get("room") or "").strip()
    if not room:
        return None
    m_room = re.search(r"Salle\s+([\w-]+)", room)
    m_wing = re.search(r"Aile\s+(?:Aile\s+)?([^,]+)", room)
    m_lvl = re.search(r"Niveau\s+(-?\d+)", room)
    return _loc(
        m_wing.group(1).strip() if m_wing else None,
        int(m_lvl.group(1)) if m_lvl else None,
        m_room.group(1) if m_room else None,
    )


def parse_orangerie(page: str) -> dict | None:
    """作品页 `<div class="location">` 里写 "Niveau -2, Salle 8 Les Arts à Paris"。"""
    m = re.search(r'class="location".*?</div>', page, re.S)
    if not m:
        return None
    text = " ".join(re.sub(r"<[^>]+>", " ", _html.unescape(m.group(0))).split())
    m_lvl = re.search(r"Niveau\s+(-?\d+)", text)
    m_room = re.search(r"Salle\s+([\w-]+)", text)
    return _loc(
        None,
        int(m_lvl.group(1)) if m_lvl else None,
        m_room.group(1) if m_room else None,
    )


def parse_parismusees(page: str) -> dict | None:
    """「Exposé : Petit Palais Rez-de-Jardin Salle 04」。"""
    m = re.search(
        r'field-name-field-oeuvre-expose.*?class="field-item(?: [^"]*)?"[^>]*>([^<]+)<',
        page,
        re.S,
    )
    if not m:
        return None
    text = _html.unescape(m.group(1)).strip()
    lvl = next((v for k, v in _PM_LEVELS.items() if k in text.lower()), None)
    m_room = re.search(r"Salle\s+([\w-]+)", text)
    return _loc(None, lvl, m_room.group(1) if m_room else None)


def _get(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read()


def _wikidata(qids: list[str]) -> dict:
    url = (
        "https://www.wikidata.org/w/api.php?action=wbgetentities&props=claims"
        "&format=json&ids=" + "|".join(qids)
    )
    return json.loads(_get(url))["entities"]


def _claims(ent: dict, pid: str) -> list[str]:
    return [
        c["mainsnak"].get("datavalue", {}).get("value")
        for c in ent.get("claims", {}).get(pid, [])
        if c["mainsnak"].get("datavalue")
    ]


def _locate(slug: str, ent: dict) -> tuple[dict | None, str]:
    """返回 (位置, 备注)。"""
    if slug == "louvre":
        ids = _claims(ent, "P9394")
        if not ids:
            return None, "Wikidata 无 P9394"
        d = json.loads(
            _get(f"https://collections.louvre.fr/ark:/53355/cl{ids[0]}.json")
        )
        loc = parse_louvre(d)
        return loc, "" if loc else "官网未给位置(可能外借/未展出)"
    domain, parser = {
        "orangerie": ("musee-orangerie.fr", parse_orangerie),
        "petit_palais": ("parismuseescollections.paris.fr", parse_parismusees),
    }.get(slug, (None, None))
    if domain is None:
        return None, "该馆没有可用的官网数据源"
    urls = [u for u in _claims(ent, "P973") if domain in u]
    if not urls:
        return None, f"Wikidata P973 无 {domain} 链接"
    url = next((u for u in urls if "/fr/" in u), urls[0])
    loc = parser(_get(url).decode("utf-8", "ignore"))
    return loc, "" if loc else "官网页无位置"


def main(slug: str) -> None:
    sys.path.insert(0, str(YAML.parent))
    from app.services.enrichment.catalog import MuseumCatalog

    qids = MuseumCatalog.from_file(YAML).get(slug).must_see
    ents = _wikidata(qids) if slug != "orsay" else {}
    print("    must_see:")
    for q in qids:
        loc, note = (None, "官网拒绝程序访问(403)") if slug == "orsay" else (None, "")
        if slug != "orsay":
            try:
                loc, note = _locate(slug, ents.get(q, {}))
            except Exception as e:  # 失败不重试,交人看
                loc, note = None, f"请求失败:{type(e).__name__}"
            time.sleep(1)
        if loc:
            parts = [f"qid: {q}"] + [
                f"{k}: {json.dumps(v, ensure_ascii=False) if isinstance(v, str) else v}"
                for k, v in loc.items()
                if v is not None
            ]
            print("      - {" + ", ".join(parts) + "}")
        else:
            print(f"      - {q}" + (f"  # {note}" if note else ""))


if __name__ == "__main__":
    main(sys.argv[1])
