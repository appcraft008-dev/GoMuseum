import pytest

from app.services.matching.people import is_artist_credit, same_person
from app.services.museum_repo import _photo_credit


@pytest.mark.parametrize(
    "a,b",
    [
        ("Desportes, Alexandre-François", "Alexandre-François Desportes"),
        ("UTRILLO Maurice", "Maurice Utrillo"),
        ("Jean león gerome", "Jean-Léon Gérôme"),
        ("Workshop of François Clouet", "François Clouet"),
        ("Attributed to Colin Nouailher", "Colin Nouailher"),
        ("Thomas Regnaudin (1622–1706)", "Thomas Regnaudin"),
        (
            "Carpeaux, Jean-Baptiste (Valenciennes, 11–05–1827 - Courbevoie, "
            "12–10–1875), sculpteur",
            "Jean-Baptiste Carpeaux",
        ),
        ("Filippino Lippi / Sandro Botticelli", "Sandro Botticelli"),
        (
            "Gaspard Marsy (1624–1681) &amp; Anselme Flamen (1647–1717)",
            "Anselme Flamen",
        ),
        ("David Teniers", "David Teniers the Younger"),  # 一边没写代际 → 仍同人
    ],
)
def test_same_person_variants(a, b):
    assert same_person(a, b)


@pytest.mark.parametrize(
    "a,b",
    [
        ("David Teniers the Elder", "David Teniers the Younger"),
        ("Pieter Brueghel l'ancien", "Pieter Brueghel le jeune"),
        ("Claude Monet", "Édouard Manet"),
        ("", "Claude Monet"),
        (None, "Claude Monet"),
    ],
)
def test_not_same_person(a, b):
    assert not same_person(a, b)


def test_master_of_year_still_hidden():
    # 名字带年份:旧的整串相等一路必须保留
    assert _photo_credit("Master of 1518", {"Master of 1518", "1518大師"}) is None


def test_reproduced_by_credit_stays_visible():
    c1 = (
        "Michel Corneille l'ancien (reproduced by : musée des Beaux-Arts de Dijon"
        " - François Jay)"
    )
    c2 = (
        "Eustache Le Sueur (reproduced by : RMN-Grand Palais (musée du Louvre)"
        " / Franck Raux"
    )
    aliases1 = {"Michel Corneille the Elder", "Michel Corneille l'ancien"}
    assert _photo_credit(c1, aliases1) == c1
    assert _photo_credit(c2, {"Eustache Le Sueur"}) == c2


def test_real_photographers_stay_visible():
    assert _photo_credit("Mbzt", {"Mesha", "메샤"}) == "Mbzt"
    assert _photo_credit("Shonagon", set()) == "Shonagon"


def test_word_order_credit_hidden():
    aliases = {"Alexandre-François Desportes"}
    assert _photo_credit("Desportes, Alexandre-François", aliases) is None
    assert is_artist_credit("Pierre-Auguste Renoir", {"RENOIR Pierre Auguste"})


def test_multiline_credit_with_uploader_stays_visible():
    # Commons 多字段:作者一行 + 上传者/摄影者一行 → 有一行不是作者就整条显示(CC 署名)
    c = "Emmanuel Frémiet\nSiren-Com"
    assert _photo_credit(c, {"Emmanuel Frémiet"}) == c


def test_misspelled_photo_marker_stays_visible():
    c = "Gabriel Blanchard; Michel Mathieu (phooto)"
    assert _photo_credit(c, {"Gabriel Blanchard"}) == c


def test_short_name_matches_full_name_only_when_subset_allowed():
    # AI 常给短名(Auguste Renoir vs 库里 Pierre-Auguste Renoir):识别加分允许子集,署名不放宽
    assert same_person("Auguste Renoir", "Pierre-Auguste Renoir", allow_subset=True)
    assert not same_person("Auguste Renoir", "Pierre-Auguste Renoir")
    assert not same_person(
        "Renoir", "Pierre-Auguste Renoir", allow_subset=True
    )  # 单词不算
    assert not same_person(
        "Pieter Brueghel the Elder", "Pieter Brueghel the Younger", allow_subset=True
    )
