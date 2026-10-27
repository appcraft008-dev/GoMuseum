"""官网展厅号解析(不联网,用存下来的官网响应片段)。spec 2026-10-27 必看打卡 §五.5。"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from fetch_rooms import (  # noqa: E402
    parse_louvre,
    parse_orangerie,
    parse_parismusees,
)

FX = Path(__file__).parent / "fixtures"


def test_louvre_room():
    d = json.loads((FX / "louvre_mona_lisa.json").read_text())
    # 源字段 "Salle 711, Aile Aile Denon, Niveau 1"(注意重复的 Aile)
    assert parse_louvre(d) == {"wing": "Denon", "level": 1, "room": "711"}


def test_louvre_empty_room_is_none():
    assert parse_louvre({"room": ""}) is None
    assert parse_louvre({}) is None


def test_orangerie_room():
    html = (FX / "orangerie_modigliani.html").read_text()
    assert parse_orangerie(html) == {"wing": None, "level": -2, "room": "8"}


def test_parismusees_room():
    html = (FX / "parismusees_les_halles.html").read_text()
    assert parse_parismusees(html) == {"wing": None, "level": -1, "room": "04"}


def test_parismusees_ground_floor_and_missing():
    html = '<div class="field-name-field-oeuvre-expose"><div class="field-item even">Petit Palais Rez-de-chaussée Salle 12</div></div>'
    assert parse_parismusees(html) == {"wing": None, "level": 0, "room": "12"}
    assert parse_parismusees("<html></html>") is None
