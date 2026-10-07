from app.services.matching.core import recognize


def _e(qid, names, artists=(), inv=None):
    return {
        "id": qid,
        "qid": qid,
        "museum_id": 1,
        "names": set(names),
        "artists": set(artists),
        "inv": inv,
        "inv_digits": None,
        "popularity": 0,
    }


IDX = [
    _e("Q_A", {"madonna and child"}, {"giovanni bellini"}),
    _e("Q_B", {"madonna and child"}, {"cima da conegliano"}),
    _e("Q_C", {"composition"}, {"piet mondrian"}),
    _e("Q_D", {"l air du soir"}, {"henri edmond cross"}),
    _e("Q_E", {"portrait of woman with dove"}, {"marie laurencin"}),
]


def test_artist_breaks_exact_title_tie():
    acc, _ = recognize(IDX, ["Madonna and Child"], [], ["Giovanni Bellini"])
    assert acc[0][0] == "Q_A" and acc[0][1] == 1.0
    assert acc[1][0] == "Q_B"


def test_short_catalog_title_not_swallowed_by_long_query():
    acc, _ = recognize(IDX, ["Composition VIII"], [], ["Wassily Kandinsky"])
    assert "Q_C" not in dict(acc)


def test_junk_returns_nothing():
    q = ["Pixelated House", "Green House Illustration"]
    acc, _ = recognize(IDX, q, [], ["Unknown"])
    assert acc == []


def test_partial_title_accepted():
    acc, _ = recognize(IDX, ["Portrait of Woman"], [], ["Marie Laurencin"])
    assert acc[0][0] == "Q_E"


def test_no_artist_needs_high_title():
    # 「Woman with a Dog」vs 库名「portrait of woman with dove」:partial≈0.8,作者没对上 → 不出
    # (⚠️ 别用「Portrait of Woman with a Dog」:整串 ratio≈0.91 会过 0.9)
    acc, _ = recognize(IDX, ["Woman with a Dog"], [], [])
    assert acc == []


def test_low_confidence_has_raw():
    acc, raw = recognize(IDX, ["Madona Chlid"], [], [])
    assert acc == [] and raw  # 有召回但不够门槛 → service 判 low_confidence


def test_inv_hit_full_score():
    idx = IDX + [_e("Q_INV", {"nothing alike"}, (), inv="rf1668")]
    acc, _ = recognize(idx, [], ["RF 1668"])
    assert acc[0] == ("Q_INV", 1.0)


def test_reverse_substring_needs_artist():
    line = "Henri-Edmond Cross L'Air du soir vers 1893 huile sur toile"
    acc, _ = recognize(IDX, [], [line])
    assert acc and acc[0][0] == "Q_D"
