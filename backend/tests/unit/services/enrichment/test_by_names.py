"""带称号人名 → 规范译名(by_names.py)。Wikidata 调用全部打桩,不联网。"""

from app.services.enrichment import by_names
from app.services.enrichment.translator import ContentTranslator

SENECA = (
    "Seneca the Younger lies in a dramatic pose. In 1476 Charles the Bold lost it. "
    "Seneca the Younger's wife watches."
)


def test_find_names_with_by_names_only():
    assert by_names.find(SENECA) == ["Seneca the Younger", "Charles the Bold"]
    assert by_names.find("The Great Wave, the elder son, Seneca.") == []


def test_resolve_drops_sentence_start_words(monkeypatch):
    # 「In Pliny the Elder」这种句首词被一起抓到时,要逐级去前缀直到精确命中
    seen = []

    def qid(name):
        seen.append(name)
        return "Q82778" if name == "Pliny the Elder" else None

    monkeypatch.setattr(by_names, "_qid", qid)
    monkeypatch.setattr(by_names, "_label", lambda q, lang: "老普林尼")
    assert by_names.resolve("In Pliny the Elder", "zh") == (
        "Pliny the Elder",
        "老普林尼",
    )
    assert seen == ["In Pliny the Elder", "Pliny the Elder"]


def test_glossary_only_for_cjk_and_fails_soft(monkeypatch):
    def resolve(name, lang):
        if "Charles" in name:
            raise TimeoutError
        return (name, "塞内卡")

    monkeypatch.setattr(by_names, "resolve", resolve)
    assert by_names.glossary(SENECA, "zh") == {"Seneca the Younger": "塞内卡"}
    assert by_names.glossary(SENECA, "fr") == {}  # 欧洲语言模型本就译对,不注入


def test_translate_section_injects_people_and_strips_tag():
    prompts = []

    def complete(system, user):
        prompts.append(system)
        return "<canonical_person>大胆的查理</canonical_person>在1476年失去了它。"

    t = ContentTranslator(
        complete, people=lambda text, lang: {"Charles the Bold": "大胆的查理"}
    )
    out = t.translate_section("Charles the Bold lost it in 1476.", "zh")
    assert (
        "Charles the Bold = <canonical_person>大胆的查理</canonical_person>"
        in prompts[0]
    )
    assert out == "大胆的查理在1476年失去了它。"


def test_translate_section_without_people_is_unchanged():
    prompts = []
    t = ContentTranslator(lambda s, u: prompts.append(s) or "x")
    t.translate_section("Charles the Bold lost it.", "zh")
    assert "canonical_person" not in prompts[0]
