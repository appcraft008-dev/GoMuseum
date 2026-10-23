"""馆封面候选/署名/外观判定(2026-10-23:小皇宫封面曾是展厅内景)。"""

import json

from app.services.enrichment import vision
from app.services.enrichment.material import (
    commons_credit,
    fetch_museum_cover_candidates,
)

FP = "http://commons.wikimedia.org/wiki/Special:FilePath/"


def test_candidates_museum_image_first_then_occupied_buildings():
    rows = [
        {"img": {"value": FP + "Building.jpg"}, "kind": {"value": "b"}},
        {"img": {"value": FP + "Museum.jpg"}, "kind": {"value": "a"}},
        {"img": {"value": FP + "Museum.jpg"}, "kind": {"value": "b"}},  # 重复去掉
    ]
    seen = {}

    def run(q):
        seen["q"] = q
        return rows

    got = fetch_museum_cover_candidates("Q59546080", run_query=run)
    assert got == [FP + "Museum.jpg", FP + "Building.jpg"]
    assert "wdt:P466 wd:Q59546080" in seen["q"]  # 建筑「被谁使用」= 这家馆


def test_candidates_reject_non_qid():
    assert fetch_museum_cover_candidates("not-a-qid", run_query=lambda q: 1 / 0) == []


def test_commons_credit_strips_html():
    meta = {
        "Artist": {
            "value": '<a href="//commons.wikimedia.org/wiki/User:X">Jane Doe</a>'
        },
        "LicenseShortName": {"value": "CC BY-SA 4.0"},
    }
    seen = {}

    def get_json(url, params):
        seen.update(params)
        return {"query": {"pages": {"1": {"imageinfo": [{"extmetadata": meta}]}}}}

    got = commons_credit(FP + "Petit%20Palais%20Paris%202.jpg", get_json=get_json)
    assert got == "Jane Doe · CC BY-SA 4.0"
    assert seen["titles"] == "File:Petit Palais Paris 2.jpg"


def test_commons_credit_missing_is_none():
    assert commons_credit(FP + "X.jpg", get_json=lambda u, p: {}) is None


def test_is_building_exterior_parses_verdict():
    def chat_fn(answer):
        return lambda model, messages, **kw: (json.dumps(answer), "m", 1, 1)

    assert vision.is_building_exterior(
        "u", chat_fn=chat_fn({"exterior": True}), image_bytes=b"x"
    )
    assert not vision.is_building_exterior(
        "u", chat_fn=chat_fn({"exterior": False}), image_bytes=b"x"
    )
