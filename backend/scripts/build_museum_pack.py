"""构建博物馆馆包（公开数据，Wikidata/Wikimedia Commons）

用法:
    python scripts/build_museum_pack.py [--museum orsay] [--limit 60]

输出 museum_packs/<slug>.json：馆元数据 + 按热度（站点链接数）排序的馆藏列表。
图片为 Wikimedia Commons 直链（公有领域/自由许可，运行时可加 ?width=600 取缩略图）。
"""

import argparse
import json
import sys
import time
from pathlib import Path

import requests

SPARQL_ENDPOINT = "https://query.wikidata.org/sparql"
USER_AGENT = "GoMuseum/0.1 (museum pack builder; contact: dev@gomuseum.app)"

MUSEUMS = {
    "orsay": {
        "qid": "Q23402",
        "name_zh": "奥赛博物馆",
        "name_en": "Musée d'Orsay",
        "city_zh": "巴黎",
        "city_en": "Paris",
        "country": "FR",
    },
}

QUERY_TEMPLATE = """
SELECT ?item ?label_zh ?label_en ?creator_zh ?creator_en ?year ?movement_zh ?movement_en ?image ?links ?inventory ?material_en ?location_en ?width ?height WHERE {{
  ?item wdt:P195 wd:{museum_qid} .
  ?item wdt:P31 wd:Q3305213 .
  ?item wdt:P18 ?image .
  ?item wikibase:sitelinks ?links .
  OPTIONAL {{ ?item rdfs:label ?label_zh . FILTER(LANG(?label_zh)="zh") }}
  OPTIONAL {{ ?item rdfs:label ?label_en . FILTER(LANG(?label_en)="en") }}
  OPTIONAL {{
    ?item wdt:P170 ?creator .
    OPTIONAL {{ ?creator rdfs:label ?creator_zh . FILTER(LANG(?creator_zh)="zh") }}
    OPTIONAL {{ ?creator rdfs:label ?creator_en . FILTER(LANG(?creator_en)="en") }}
  }}
  OPTIONAL {{ ?item wdt:P571 ?date . BIND(YEAR(?date) AS ?year) }}
  OPTIONAL {{
    ?item wdt:P135 ?movement .
    OPTIONAL {{ ?movement rdfs:label ?movement_zh . FILTER(LANG(?movement_zh)="zh") }}
    OPTIONAL {{ ?movement rdfs:label ?movement_en . FILTER(LANG(?movement_en)="en") }}
  }}
  OPTIONAL {{ ?item wdt:P217 ?inventory }}
  OPTIONAL {{ ?item wdt:P186 ?material . OPTIONAL {{ ?material rdfs:label ?material_en . FILTER(LANG(?material_en)="en") }} }}
  OPTIONAL {{ ?item wdt:P276 ?location . OPTIONAL {{ ?location rdfs:label ?location_en . FILTER(LANG(?location_en)="en") }} }}
  OPTIONAL {{ ?item wdt:P2049 ?width }}
  OPTIONAL {{ ?item wdt:P2048 ?height }}
}}
ORDER BY DESC(?links)
LIMIT {limit}
"""


def _value(row: dict, key: str) -> str | None:
    return row.get(key, {}).get("value")


def build_pack(slug: str, limit: int) -> dict:
    museum = MUSEUMS[slug]
    # 用 5 倍缓冲：creator/movement/material/location 等都是多值属性，会让单件作品产生多行，
    # 服务端 LIMIT 作用在膨胀后的行上；缓冲不足可能导致去重后不足 limit 件。
    query = QUERY_TEMPLATE.format(museum_qid=museum["qid"], limit=limit * 5)
    resp = requests.get(
        SPARQL_ENDPOINT,
        params={"format": "json", "query": query},
        headers={"User-Agent": USER_AGENT},
        timeout=60,
    )
    resp.raise_for_status()
    rows = resp.json()["results"]["bindings"]

    artworks: list[dict] = []
    seen_qids: set[str] = set()
    for row in rows:
        qid = _value(row, "item").rsplit("/", 1)[-1]
        if (
            qid in seen_qids
        ):  # creator/movement/material/location 多值 OPTIONAL 会产生重复行，取首行值
            continue
        seen_qids.add(qid)
        title_zh = _value(row, "label_zh")
        title_en = _value(row, "label_en")
        if not (title_zh or title_en):
            continue
        artworks.append(
            {
                "qid": qid,
                "title_zh": title_zh or title_en,
                "title_en": title_en or title_zh,
                "artist_zh": _value(row, "creator_zh")
                or _value(row, "creator_en")
                or "佚名",
                "artist_en": _value(row, "creator_en")
                or _value(row, "creator_zh")
                or "Unknown",
                "year": _value(row, "year"),
                "period_zh": _value(row, "movement_zh") or "19世纪",
                "period_en": _value(row, "movement_en") or "19th century",
                "image": (_value(row, "image") or "").replace("http://", "https://"),
                "popularity": int(_value(row, "links") or 0),
                "inventory_number": _value(row, "inventory"),
                "attributes": {
                    "material": _value(row, "material_en"),
                    "current_location": _value(row, "location_en"),
                    "width_cm": _value(row, "width"),
                    "height_cm": _value(row, "height"),
                },
            }
        )
        if len(artworks) >= limit:
            break

    return {
        "slug": slug,
        "qid": museum["qid"],
        "name_zh": museum["name_zh"],
        "name_en": museum["name_en"],
        "city_zh": museum["city_zh"],
        "city_en": museum["city_en"],
        "country": museum["country"],
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "source": "Wikidata/Wikimedia Commons (public data)",
        "artwork_count": len(artworks),
        "artworks": artworks,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--museum", default="orsay", choices=MUSEUMS.keys())
    parser.add_argument("--limit", type=int, default=60)
    args = parser.parse_args()

    pack = build_pack(args.museum, args.limit)
    out_dir = Path(__file__).resolve().parent.parent / "museum_packs"
    out_dir.mkdir(exist_ok=True)
    out_path = out_dir / f"{args.museum}.json"
    out_path.write_text(json.dumps(pack, ensure_ascii=False, indent=2))
    print(f"✓ {out_path}: {pack['artwork_count']} artworks")
    for art in pack["artworks"][:5]:
        print(
            f"  - {art['title_zh']} | {art['artist_zh']} | {art['year']} | 热度 {art['popularity']}"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
