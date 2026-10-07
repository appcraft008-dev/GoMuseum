"""匹配评测的公共 fixture:prod 目录抽样 → 与 search.inprocess._build_global 同字段的索引条目。"""

import json
import re
from pathlib import Path

import pytest

from app.services.matching.normalize import normalize, normalize_inv

HERE = Path(__file__).parent


def load_jsonl(p):
    return [json.loads(line) for line in open(p, encoding="utf-8") if line.strip()]


def to_entries(cat):
    out = []
    for d in cat:
        raw = {v for v in (d.get("i18n") or {}).values() if v}
        raw |= {x for x in (d.get("en"), d.get("zh")) if x}
        arts = {v for v in (d.get("a_i18n") or {}).values() if v}
        arts |= {x for x in (d.get("a_en"), d.get("a_zh"), d.get("a_name_en")) if x}
        out.append(
            {
                "id": d["qid"],
                "qid": d["qid"],
                "museum_id": d["m"],
                "names": {normalize(x) for x in raw} - {""},
                "artists": {normalize(a) for a in arts} - {""},
                "inv": normalize_inv(d.get("inv")) or None,
                "inv_digits": re.sub(r"\D", "", d.get("inv") or "") or None,
                "popularity": d.get("pop") or 0,
            }
        )
    return out


@pytest.fixture(scope="session")
def eval_catalog():
    return load_jsonl(HERE / "catalog_sample.jsonl")


@pytest.fixture()
def eval_index(eval_catalog):
    return to_entries(eval_catalog)
