import pytest

from app.services.enrichment.lang_detect import text_in_language


@pytest.mark.parametrize(
    "text,lang,expected",
    [
        ("这是一段完整的中文讲解，介绍这幅画的历史与技法内容。", "zh", True),
        ("This is a complete English paragraph about the painting here.", "en", True),
        (
            "Claude Monet, né en 1840 à Paris, est un peintre français reconnu.",
            "en",
            False,
        ),
        ("约翰·施洗者的 severed head 悬浮在空中，这是一段较长的中文讲解。", "zh", True),
        ("What did Van Gogh's letters reveal about this piece of art?", "zh", False),
        ("Monet", "en", True),
        ("1855", "zh", True),
    ],
)
def test_text_in_language(text, lang, expected):
    assert text_in_language(text, lang) is expected


def test_language_agnostic_all_default_languages():
    from app.services.enrichment.lang_config import DEFAULT_LANGUAGES

    samples = {
        "en": "A long English sentence here about art history and painting technique.",
        "fr": "Une longue phrase française sur l'histoire de l'art et la technique picturale.",
        "de": "Ein langer deutscher Satz über Kunstgeschichte und Maltechnik steht hier.",
        "es": "Una larga frase en español sobre la historia del arte y la técnica pictórica.",
        "it": "Una lunga frase italiana sulla storia dell'arte e la tecnica pittorica qui.",
        "pl": "Długie polskie zdanie o historii sztuki i technice malarskiej tutaj przedstawione.",
        "zh": "这是一段较长的中文文本，讲述艺术史与绘画技法的相关内容。",
        "zh-hant": "這是一段較長的中文文本，講述藝術史與繪畫技法的相關內容。",
        "ja": "これは美術史と絵画技法について述べる、やや長めの日本語の文章です。",
        "ko": "이것은 미술사와 회화 기법에 대해 설명하는 다소 긴 한국어 문장입니다.",
    }
    for lang in DEFAULT_LANGUAGES:
        assert text_in_language(samples[lang], lang) is True, lang
