"""一次性:从 Wikidata 实取并裁剪测试夹具(spec §6:夹具取真实返回,不手编)。
重跑会刷新数据,测试里的期望值以提交进库的 entities.json 为准。"""

import json
from pathlib import Path

import requests

UA = "GoMuseum/0.1 (enrichment; contact: dev@gomuseum.app)"
API = "https://www.wikidata.org/w/api.php"
LANGS = [
    "en",
    "fr",
    "de",
    "es",
    "it",
    "ja",
    "ko",
    "pt",
    "zh",
    "zh-hans",
    "zh-cn",
    "zh-hant",
    "zh-tw",
    "zh-hk",
]
KEEP_PROPS = {
    "P170",
    "P569",
    "P570",
    "P27",
    "P800",
    "P88",
    "P180",
    "P186",
    "P135",
    "P136",
    "P1343",
    "P4969",
    "P144",
    "P941",
    "P361",
}
FULL = ["Q64309678", "Q104479426", "Q12418", "Q35548", "Q5597"]


def get(ids, props, langs=None):
    p = {
        "action": "wbgetentities",
        "format": "json",
        "ids": "|".join(ids),
        "props": props,
    }
    if langs:
        p["languages"] = "|".join(langs)
    r = requests.get(API, params=p, headers={"User-Agent": UA}, timeout=30)
    r.raise_for_status()
    return r.json()["entities"]


out = {}
for q, e in get(FULL, "labels|claims|sitelinks", LANGS).items():
    e["claims"] = {p: v for p, v in e.get("claims", {}).items() if p in KEEP_PROPS}
    e["sitelinks"] = {
        k: v
        for k, v in e.get("sitelinks", {}).items()
        if k in ("enwiki", "frwiki", "itwiki")
    }
    out[q] = e
value_ids = sorted(
    {
        s["mainsnak"]["datavalue"]["value"]["id"]
        for e in out.values()
        for p, sts in e["claims"].items()
        if p != "P170"
        for s in sts
        if s["mainsnak"].get("snaktype") == "value"
        and s["mainsnak"]["datavalue"]["type"] == "wikibase-entityid"
    }
)
for i in range(0, len(value_ids), 50):
    for q, e in get(value_ids[i : i + 50], "labels", LANGS).items():
        out.setdefault(q, {"id": q, "labels": e.get("labels", {})})
Path(__file__).with_name("entities.json").write_text(
    json.dumps(out, ensure_ascii=False, indent=1, sort_keys=True)
)
print(len(out), "entities")
