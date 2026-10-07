from app.services.matching.normalize import normalize, normalize_inv, tokens
from app.services.recognition import matcher


def test_normalize_unchanged_behaviour():
    assert normalize("Théodore, Géricault!") == "theodore gericault"
    assert normalize_inv("RF 1668") == "rf1668"
    assert normalize_inv(None) == ""


def test_matcher_reexports_same_functions():
    assert matcher.normalize is normalize
    assert matcher.normalize_inv is normalize_inv


def test_tokens_latin_split_on_space():
    assert tokens("l air du soir") == ["l", "air", "du", "soir"]


def test_tokens_cjk_bigrams():
    assert tokens("世界的起源") == ["世界", "界的", "的起", "起源"]
    assert tokens("梵") == ["梵"]  # 单字保留为一个词
    assert tokens("文森特 梵高") == ["文森", "森特", "梵高"]
