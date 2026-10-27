"""必看清单与官网地址的真相源是 museums.yaml(spec 2026-10-22-website-v1 §6)。"""

from app.services.museum_repo import museum_website
from app.services.must_see import MUST_SEE


def test_must_see_matches_yaml():
    assert MUST_SEE["louvre"][0] == "Q12418"
    assert len(MUST_SEE["orsay"]) == 23
    assert MUST_SEE["petit_palais"][-1] == "Q99472451"
    assert "rijksmuseum" not in MUST_SEE


def test_museum_website():
    assert museum_website("louvre").startswith("https://")
    assert museum_website("nope") is None


def test_must_see_entry_accepts_dict_with_location(tmp_path):
    from app.services.enrichment.catalog import MuseumCatalog

    p = tmp_path / "m.yaml"
    p.write_text(
        "museums:\n  x:\n    name_zh: 馆\n    name_en: X\n    city_zh: 城\n"
        "    city_en: C\n    country: FR\n    wikidata_qid: Q1\n"
        "    category_filter: Q3305213\n    fetch_limit: 5\n    sample_size: 2\n"
        "    must_see:\n"
        "      - Q1\n"
        "      - {qid: Q2, wing: Denon, level: 1, room: 711}\n"
        "      - {qid: Q3}\n",
        encoding="utf-8",
    )
    cfg = MuseumCatalog.from_file(p).get("x")
    assert cfg.must_see == ["Q1", "Q2", "Q3"]
    # room 在 yaml 里写成数字也按字符串收(厅号可能是 "04" 这种)
    assert cfg.must_see_locations == {
        "Q2": {"wing": "Denon", "level": 1, "room": "711"}
    }


def test_must_see_location_exported():
    from app.services.must_see import MUST_SEE_LOCATION

    assert isinstance(MUST_SEE_LOCATION, dict)
