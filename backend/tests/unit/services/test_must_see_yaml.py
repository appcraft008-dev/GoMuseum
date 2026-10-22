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
