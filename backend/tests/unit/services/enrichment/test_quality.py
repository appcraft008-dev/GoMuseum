from app.services.enrichment.quality import _split_sentences


def test_split_sentences_basic():
    text = "Olympia is a painting. It caused a scandal. Monet led a subscription."
    assert _split_sentences(text) == [
        "Olympia is a painting.",
        "It caused a scandal.",
        "Monet led a subscription.",
    ]


def test_split_sentences_strips_empty_and_whitespace():
    assert _split_sentences("  One sentence only.  ") == ["One sentence only."]
    assert _split_sentences("") == []
    assert _split_sentences(None) == []
